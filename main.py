# main.py
import os
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from enum import Enum
from pydantic import BaseModel, Field, EmailStr
import uuid
import json
import time
from groq import Groq
import pinecone
from sentence_transformers import SentenceTransformer
from dotenv import load_dotenv
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import httpx
import requests
import schedule
import threading
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("insurance_outreach")

# ----- Models -----
class IndustryType(str, Enum):
    TECH = "tech"
    FINANCE = "finance"
    HEALTHCARE = "healthcare"
    RETAIL = "retail"
    MANUFACTURING = "manufacturing"
    EDUCATION = "education"
    CONSTRUCTION = "construction"
    ENERGY = "energy"
    HOSPITALITY = "hospitality"
    TRANSPORTATION = "transportation"

class EngagementLevel(str, Enum):
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"

class OutreachChannel(str, Enum):
    EMAIL = "email"
    CALL = "call"
    BOTH = "both"

class OutreachStatus(str, Enum):
    PENDING = "pending"
    SENT = "sent"
    OPENED = "opened"
    CLICKED = "clicked"
    RESPONDED = "responded"
    FAILED = "failed"

class Prospect(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    company_name: str
    industry: IndustryType
    contact_name: str
    email: EmailStr
    phone: Optional[str] = None
    engagement_level: EngagementLevel = EngagementLevel.NONE
    notes: str = ""
    last_contact: Optional[datetime] = None
    preferred_channel: OutreachChannel = OutreachChannel.EMAIL
    objections: List[str] = []
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

class OutreachHistory(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    prospect_id: str
    timestamp: datetime = Field(default_factory=datetime.now)
    channel: OutreachChannel
    content: Dict[str, Any] = {}  # Changed from Dict[str, str] to allow for nested dictionaries
    status: OutreachStatus = OutreachStatus.PENDING
    response: Optional[str] = None
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

class ProspectDatabase:
    def __init__(self, db_path="prospects.json"):
        self.db_path = db_path
        self.prospects = {}
        self.history = {}
        self._load_db()
    
    def _load_db(self):
        if os.path.exists(self.db_path):
            try:
                with open(self.db_path, 'r') as f:
                    data = json.load(f)
                    self.prospects = {k: Prospect(**v) for k, v in data.get('prospects', {}).items()}
                    self.history = {k: OutreachHistory(**v) for k, v in data.get('history', {}).items()}
            except Exception as e:
                logger.error(f"Error loading database: {str(e)}")
                # Initialize empty dictionaries if loading fails
                self.prospects = {}
                self.history = {}
        self._save_db()
    
    def _save_db(self):
        try:
            with open(self.db_path, 'w') as f:
                json.dump({
                    'prospects': {k: v.dict() for k, v in self.prospects.items()},
                    'history': {k: v.dict() for k, v in self.history.items()}
                }, f, indent=2, default=str)
        except Exception as e:
            logger.error(f"Error saving database: {str(e)}")
    
    def add_prospect(self, prospect: Prospect):
        self.prospects[prospect.id] = prospect
        self._save_db()
        return prospect.id
    
    def update_prospect(self, prospect_id: str, data: Dict):
        if prospect_id in self.prospects:
            prospect_dict = self.prospects[prospect_id].dict()
            prospect_dict.update(data)
            self.prospects[prospect_id] = Prospect(**prospect_dict)
            self._save_db()
            return True
        return False
    
    def get_prospect(self, prospect_id: str) -> Optional[Prospect]:
        return self.prospects.get(prospect_id)
    
    def list_prospects(self, filters: Dict = None) -> List[Prospect]:
        if not filters:
            return list(self.prospects.values())
        
        results = []
        for prospect in self.prospects.values():
            match = True
            for key, value in filters.items():
                if getattr(prospect, key, None) != value:
                    match = False
                    break
            if match:
                results.append(prospect)
        return results
    
    def add_history(self, history: OutreachHistory):
        self.history[history.id] = history
        if history.prospect_id in self.prospects:
            self.prospects[history.prospect_id].last_contact = history.timestamp
        self._save_db()
        return history.id
    
    def update_history(self, history_id: str, data: Dict):
        if history_id in self.history:
            history_dict = self.history[history_id].dict()
            history_dict.update(data)
            self.history[history_id] = OutreachHistory(**history_dict)
            self._save_db()
            return True
        return False
    
    def get_history(self, history_id: str) -> Optional[OutreachHistory]:
        return self.history.get(history_id)
    
    def get_prospect_history(self, prospect_id: str) -> List[OutreachHistory]:
        return [h for h in self.history.values() if h.prospect_id == prospect_id]

# ----- Groq LLM Integration -----
class GroqLLM:
    def __init__(self):
        api_key = os.getenv("GROQ_API_KEY")
        http_client = httpx.Client()
        self.client = Groq(api_key=api_key, http_client=http_client)
        self.embedding_model = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')
        self.retry_attempts = 3
        self.retry_delay = 2
    
    def generate(self, prompt: str, context: str = "", system_prompt: str = "") -> str:
        for attempt in range(self.retry_attempts):
            try:
                messages = []
                
                if system_prompt:
                    messages.append({
                        "role": "system",
                        "content": system_prompt
                    })
                
                messages.append({
                    "role": "user",
                    "content": f"Context: {context}\n\n{prompt}"
                })
                
                response = self.client.chat.completions.create(
                    messages=messages,
                    model="llama3-70b-8192",
                    temperature=0.7,
                    max_tokens=1024
                )
                return response.choices[0].message.content
            except Exception as e:
                logger.error(f"Groq API error (attempt {attempt+1}): {str(e)}")
                if attempt < self.retry_attempts - 1:
                    time.sleep(self.retry_delay)
                else:
                    return "I was unable to generate a response at this time. Please try again later."
    
    def embed_text(self, text: str) -> List[float]:
        for attempt in range(self.retry_attempts):
            try:
                return self.embedding_model.encode(text).tolist()
            except Exception as e:
                logger.error(f"Embedding error (attempt {attempt+1}): {str(e)}")
                if attempt < self.retry_attempts - 1:
                    time.sleep(self.retry_delay)
                else:
                    # Return a zero vector as fallback
                    return [0.0] * 384  # Default dimensionality for the model

# ----- Knowledge Base -----
class InsuranceKnowledgeBase:
    def __init__(self):
        self.llm = GroqLLM()
        self.initialized = False
        try:
            api_key = os.getenv("PINECONE_API_KEY")
            env = os.getenv("PINECONE_ENV")
            
            if not api_key or not env:
                logger.warning("Pinecone API key or environment not set")
                return
                
            pinecone.init(
                api_key=api_key,
                environment=env
            )
            
            # Check if index exists, create if it doesn't
            existing_indexes = pinecone.list_indexes()
            if "insurance-knowledge" not in existing_indexes:
                self._initialize_knowledge_base()
            
            self.index = pinecone.Index("insurance-knowledge")
            self.initialized = True
        except Exception as e:
            logger.error(f"Pinecone initialization error: {str(e)}")
            # We'll fall back to a simpler approach if Pinecone isn't available
    
    def _initialize_knowledge_base(self):
        # Create index with appropriate dimension
        pinecone.create_index(
            name="insurance-knowledge",
            dimension=384,  # Dimension of the embedding model
            metric="cosine"
        )
        index = pinecone.Index("insurance-knowledge")
        
        # Add initial insurance knowledge (would be expanded in production)
        industry_knowledge = {
            "tech": [
                "Tech companies face unique cybersecurity risks related to data breaches.",
                "Intellectual property insurance protects tech innovations and software.",
                "Business interruption coverage is critical for SaaS and cloud services.",
                "Tech startups often need specialized E&O insurance for their digital products."
            ],
            "finance": [
                "Financial institutions require comprehensive fraud protection and cyber liability.",
                "Professional liability coverage protects against claims of financial mismanagement.",
                "D&O insurance is essential for finance executives facing regulatory scrutiny.",
                "Finance companies need comprehensive coverage for digital assets and transactions."
            ],
            "healthcare": [
                "Healthcare organizations need HIPAA-compliant cyber liability coverage.",
                "Medical malpractice insurance protects healthcare providers against claims.",
                "Healthcare facilities require specialized property insurance for medical equipment.",
                "Telemedicine providers need tailored E&O coverage for digital health services."
            ],
            "retail": [
                "Retailers need comprehensive general liability for customer injuries on premises.",
                "Product liability insurance protects retailers from claims related to sold goods.",
                "Business interruption insurance is vital for protecting against supply chain disruptions.",
                "Retail businesses need specialized coverage for inventory and seasonal fluctuations."
            ],
            "manufacturing": [
                "Manufacturing businesses need equipment breakdown and business interruption coverage.",
                "Product liability insurance is essential for manufacturers to protect against defect claims.",
                "Workers' compensation is critical due to higher injury rates in manufacturing.",
                "Environmental liability coverage protects against pollution risks in manufacturing."
            ]
        }
        
        # Upsert vectors
        vectors = []
        for industry, facts in industry_knowledge.items():
            for i, fact in enumerate(facts):
                embedding = self.llm.embed_text(f"{industry} {fact}")
                vectors.append({
                    "id": f"{industry}-{i}",
                    "values": embedding,
                    "metadata": {
                        "industry": industry,
                        "text": fact
                    }
                })
        
        # Batch upsert
        index.upsert(vectors=vectors)
        logger.info(f"Initialized knowledge base with {len(vectors)} vectors")
    
    def query_knowledge(self, query: str, industry: str, top_k: int = 5) -> str:
        try:
            if not self.initialized:
                # Fall back to static knowledge if Pinecone isn't initialized
                return self._get_static_knowledge(industry)
                
            # Semantic search
            query_embedding = self.llm.embed_text(f"{industry} {query}")
            results = self.index.query(
                vector=query_embedding,
                top_k=top_k,
                include_metadata=True
            )
            
            # Format context with industry-specific weighting
            matches = results.matches
            
            # Prioritize industry-specific matches
            industry_matches = [m for m in matches if m.metadata.get("industry") == industry]
            other_matches = [m for m in matches if m.metadata.get("industry") != industry]
            
            # Combine them with industry matches first
            ordered_matches = industry_matches + other_matches
            
            context = "\n".join(
                [f"- {match.metadata['text']}" for match in ordered_matches]
            )
            return context
        except Exception as e:
            logger.error(f"Knowledge query error: {str(e)}")
            return self._get_static_knowledge(industry)
    
    def _get_static_knowledge(self, industry: str) -> str:
        """Fallback method for when Pinecone is not available."""
        industry_knowledge = {
            "tech": [
                "Tech companies face unique cybersecurity risks related to data breaches.",
                "Intellectual property insurance protects tech innovations and software.",
                "Business interruption coverage is critical for SaaS and cloud services.",
                "Tech startups often need specialized E&O insurance for their digital products."
            ],
            "finance": [
                "Financial institutions require comprehensive fraud protection and cyber liability.",
                "Professional liability coverage protects against claims of financial mismanagement.",
                "D&O insurance is essential for finance executives facing regulatory scrutiny.",
                "Finance companies need comprehensive coverage for digital assets and transactions."
            ],
            "healthcare": [
                "Healthcare organizations need HIPAA-compliant cyber liability coverage.",
                "Medical malpractice insurance protects healthcare providers against claims.",
                "Healthcare facilities require specialized property insurance for medical equipment.",
                "Telemedicine providers need tailored E&O coverage for digital health services."
            ],
            "retail": [
                "Retailers need comprehensive general liability for customer injuries on premises.",
                "Product liability insurance protects retailers from claims related to sold goods.",
                "Business interruption insurance is vital for protecting against supply chain disruptions.",
                "Retail businesses need specialized coverage for inventory and seasonal fluctuations."
            ],
            "manufacturing": [
                "Manufacturing businesses need equipment breakdown and business interruption coverage.",
                "Product liability insurance is essential for manufacturers to protect against defect claims.",
                "Workers' compensation is critical due to higher injury rates in manufacturing.",
                "Environmental liability coverage protects against pollution risks in manufacturing."
            ]
        }
        
        # Default to tech if industry not found
        facts = industry_knowledge.get(industry, industry_knowledge["tech"])
        return "\n".join([f"- {fact}" for fact in facts])
    
    def add_knowledge(self, text: str, industry: str, metadata: Dict = None):
        try:
            if not self.initialized:
                logger.warning("Cannot add knowledge - Pinecone not initialized")
                return None
                
            if metadata is None:
                metadata = {}
            
            # Create unique ID
            knowledge_id = f"{industry}-{uuid.uuid4()}"
            
            # Get embedding
            embedding = self.llm.embed_text(f"{industry} {text}")
            
            # Prepare metadata
            meta = {
                "industry": industry,
                "text": text,
                "timestamp": datetime.now().isoformat()
            }
            meta.update(metadata)
            
            # Upsert to index
            self.index.upsert(
                vectors=[{
                    "id": knowledge_id,
                    "values": embedding,
                    "metadata": meta
                }]
            )
            
            return knowledge_id
        except Exception as e:
            logger.error(f"Error adding knowledge: {str(e)}")
            return None

# ----- Content Generation -----
class OutreachGenerator:
    def __init__(self):
        self.llm = GroqLLM()
        self.knowledge_base = InsuranceKnowledgeBase()
    
    def _get_industry_system_prompt(self, industry: IndustryType) -> str:
        """Generate industry-specific system prompt for better personalization."""
        industry_prompts = {
            IndustryType.TECH: """You are an insurance specialist who understands the unique needs of technology companies. 
            Emphasize cybersecurity, intellectual property protection, and business continuity. Use tech-savvy language 
            and reference innovation, scalability, and digital transformation.""",
            
            IndustryType.FINANCE: """You are an insurance expert specializing in financial services. 
            Focus on regulatory compliance, fraud protection, and fiduciary responsibility. Use precise, 
            professional language and emphasize ROI, risk management, and security.""",
            
            IndustryType.HEALTHCARE: """You are an insurance advisor with deep expertise in healthcare regulations.
            Highlight HIPAA compliance, malpractice coverage, and patient data protection. Use compassionate, 
            ethical language that acknowledges the critical nature of healthcare services.""",
            
            IndustryType.RETAIL: """You are an insurance consultant who understands retail businesses.
            Focus on premises liability, inventory protection, and seasonal business fluctuations. Use 
            approachable language that acknowledges customer experience and supply chain challenges.""",
            
            IndustryType.MANUFACTURING: """You are an insurance specialist for manufacturing operations.
            Emphasize equipment breakdown, product liability, and workers' compensation. Use practical language
            that acknowledges production efficiency and supply chain reliability."""
        }
        
        return industry_prompts.get(industry, """You are a professional insurance consultant who tailors 
        solutions to each client's specific industry and needs. Use clear, helpful language that demonstrates 
        industry knowledge and focuses on client-specific value.""")
    
    def _get_engagement_instructions(self, level: EngagementLevel) -> str:
        """Generate instructions based on prospect's engagement level."""
        engagement_instructions = {
            EngagementLevel.NONE: "This is a first contact, so introduce the company and value proposition concisely.",
            EngagementLevel.LOW: "The prospect has minimal engagement history. Reference any previous contact briefly and provide new value.",
            EngagementLevel.MEDIUM: "The prospect has shown interest. Reference previous interactions and deepen the relationship with specific solutions.",
            EngagementLevel.HIGH: "The prospect is highly engaged. Use a familiar tone, reference previous discussions, and move toward conversion."
        }
        
        return engagement_instructions.get(level, "Introduce yourself and your company's value proposition.")
    
    def _handle_objections(self, objections: List[str]) -> str:
        """Generate content to address known objections."""
        if not objections:
            return ""
        
        objection_text = "\n".join([f"- They have previously expressed concerns about: {obj}" for obj in objections])
        return f"Address these potential objections tactfully:\n{objection_text}"
    
    def generate_email(self, prospect: Prospect) -> Dict[str, str]:
        # Get relevant industry knowledge
        context = self.knowledge_base.query_knowledge(
            query=f"{prospect.company_name} {prospect.notes}",
            industry=prospect.industry.value
        )
        
        # Industry-specific system prompt
        system_prompt = self._get_industry_system_prompt(prospect.industry)
        
        # Get engagement-specific instructions
        engagement_instructions = self._get_engagement_instructions(prospect.engagement_level)
        
        # Handle objections
        objection_handling = self._handle_objections(prospect.objections)
        
        prompt = f"""Generate a personalized insurance outreach email for:
        Company: {prospect.company_name}
        Industry: {prospect.industry.value}
        Contact: {prospect.contact_name}
        Engagement Level: {prospect.engagement_level.value}
        Notes: {prospect.notes}
        
        Instructions:
        {engagement_instructions}
        {objection_handling}
        
        Make the email concise (3-4 paragraphs max), personalized to their industry, and include:
        1. A specific insight about their industry or company type
        2. A clear value proposition tailored to their business
        3. A soft call-to-action appropriate to their engagement level
        
        Format:
        Subject: [Engaging, personalized subject line - NO PLACEHOLDERS]
        Body: [Email body with personal greeting and signature]"""
        
        response = self.llm.generate(prompt, context, system_prompt)
        return self._parse_response(response)
    
    def generate_call_script(self, prospect: Prospect) -> Dict[str, str]:
        # Get relevant industry knowledge
        context = self.knowledge_base.query_knowledge(
            query=f"{prospect.company_name} {prospect.notes}",
            industry=prospect.industry.value
        )
        
        # Industry-specific system prompt
        system_prompt = self._get_industry_system_prompt(prospect.industry)
        
        # Get engagement-specific instructions
        engagement_instructions = self._get_engagement_instructions(prospect.engagement_level)
        
        # Handle objections
        objection_handling = self._handle_objections(prospect.objections)
        
        prompt = f"""Generate a personalized insurance cold call script for:
        Company: {prospect.company_name}
        Industry: {prospect.industry.value}
        Contact: {prospect.contact_name}
        Engagement Level: {prospect.engagement_level.value}
        Notes: {prospect.notes}
        
        Instructions:
        {engagement_instructions}
        {objection_handling}
        
        Create a natural, conversational script that includes:
        1. A brief introduction that establishes credibility
        2. An industry-specific insight that demonstrates understanding
        3. A question to engage the prospect
        4. Clear value proposition tailored to their business
        5. Handling for common objections
        6. A clear next step proposal
        
        Format:
        Introduction: [Brief introduction]
        Key Talking Points: [Bullet points for key value propositions]
        Questions: [2-3 engaging questions to ask]
        Objection Handling: [How to handle common objections]
        Close: [How to end the call with next steps]"""
        
        response = self.llm.generate(prompt, context, system_prompt)
        return self._parse_call_script(response)
    
    def generate_follow_up(self, prospect: Prospect, previous_history: List[OutreachHistory]) -> Dict[str, str]:
        # Extract previous interactions for context
        previous_interactions = "\n".join([
            f"- {h.timestamp.strftime('%Y-%m-%d')}: {h.channel.value.upper()} - Status: {h.status.value}" +
            (f" - Response: {h.response}" if h.response else "")
            for h in previous_history
        ])
        
        # Get relevant industry knowledge
        context = self.knowledge_base.query_knowledge(
            query=f"{prospect.company_name} {prospect.notes} follow up",
            industry=prospect.industry.value
        )
        
        # Industry-specific system prompt
        system_prompt = self._get_industry_system_prompt(prospect.industry)
        
        prompt = f"""Generate a personalized follow-up email for:
        Company: {prospect.company_name}
        Industry: {prospect.industry.value}
        Contact: {prospect.contact_name}
        Engagement Level: {prospect.engagement_level.value}
        Notes: {prospect.notes}
        
        Previous Interactions:
        {previous_interactions}
        
        Instructions:
        - Reference previous communications appropriately
        - Provide new value or insight in this follow-up
        - Keep it concise but personalized
        - Include a clear, low-friction next step
        
        Format:
        Subject: [Follow-up subject line - NO PLACEHOLDERS]
        Body: [Email body with personal greeting and signature]"""
        
        response = self.llm.generate(prompt, context, system_prompt)
        return self._parse_response(response)
    
    def generate_engagement_advice(self, prospect: Prospect, history: List[OutreachHistory]) -> str:
        """Generate advice for sales team on how to further engage this prospect."""
        # Extract previous interactions for context
        previous_interactions = "\n".join([
            f"- {h.timestamp.strftime('%Y-%m-%d')}: {h.channel.value.upper()} - Status: {h.status.value}" +
            (f" - Response: {h.response}" if h.response else "")
            for h in history
        ])
        
        # Get relevant industry knowledge
        context = self.knowledge_base.query_knowledge(
            query=f"{prospect.company_name} {prospect.notes} sales strategy",
            industry=prospect.industry.value
        )
        
        prompt = f"""As an insurance sales strategist, provide advice on how to further engage:
        Company: {prospect.company_name}
        Industry: {prospect.industry.value}
        Contact: {prospect.contact_name}
        Current Engagement Level: {prospect.engagement_level.value}
        Notes: {prospect.notes}
        
        Previous Interactions:
        {previous_interactions}
        
        Provide specific, actionable advice to the sales team on:
        1. Recommended next steps
        2. Potential pain points to address
        3. Industry-specific talking points that might resonate
        4. Timing recommendations for follow-up
        5. Suggested communication channel(s)"""
        
        return self.llm.generate(prompt, context)
    
    def _parse_response(self, response: str) -> Dict[str, str]:
        subject = "Personalized Insurance Solution"
        body = ""
        
        if "Subject:" in response:
            parts = response.split("Subject:", 1)
            subject_parts = parts[1].split("\n", 1)
            subject = subject_parts[0].strip()
            
            if "Body:" in response:
                body_parts = response.split("Body:", 1)
                body = body_parts[1].strip()
            else:
                # If no explicit Body tag, use everything after the subject line
                body = subject_parts[1].strip() if len(subject_parts) > 1 else ""
        else:
            # If no format tags, use whole response as body
            body = response.strip()
        
        return {"subject": subject, "body": body}
    
    def _parse_call_script(self, response: str) -> Dict[str, str]:
        sections = {
            "introduction": "",
            "key_points": "",
            "questions": "",
            "objection_handling": "",
            "close": ""
        }
        
        current_section = None
        section_text = []
        
        for line in response.split("\n"):
            line = line.strip()
            if not line:
                continue
            
            if "Introduction:" in line:
                current_section = "introduction"
                line = line.replace("Introduction:", "").strip()
            elif "Key Talking Points:" in line or "Key Points:" in line:
                if current_section and section_text:
                    sections[current_section] = "\n".join(section_text)
                current_section = "key_points"
                section_text = []
                continue
            elif "Questions:" in line:
                if current_section and section_text:
                    sections[current_section] = "\n".join(section_text)
                current_section = "questions"
                section_text = []
                continue
            elif "Objection Handling:" in line or "Objections:" in line:
                if current_section and section_text:
                    sections[current_section] = "\n".join(section_text)
                current_section = "objection_handling"
                section_text = []
                continue
            elif "Close:" in line:
                if current_section and section_text:
                    sections[current_section] = "\n".join(section_text)
                current_section = "close"
                section_text = []
                continue
            
            if current_section:
                section_text.append(line)
        
        # Add the last section
        if current_section and section_text:
            sections[current_section] = "\n".join(section_text)
        
        # If parsing failed, use the whole response as the script
        if all(not v for v in sections.values()):
            sections["full_script"] = response.strip()
        
        return sections

# ----- Email Service -----
class EmailService:
    def __init__(self):
        self.smtp_server = os.getenv("SMTP_SERVER", "smtp.gmail.com")
        self.smtp_port = int(os.getenv("SMTP_PORT", "587"))
        self.smtp_username = os.getenv("SMTP_USERNAME", "")
        self.smtp_password = os.getenv("SMTP_PASSWORD", "")
        self.sender_email = os.getenv("SENDER_EMAIL", self.smtp_username)
        self.sender_name = os.getenv("SENDER_NAME", "Insurance Solutions")
        self.tracking_domain = os.getenv("TRACKING_DOMAIN", "track.insuranceco.com")
    
    def send_email(self, prospect: Prospect, content: Dict[str, str], history_id: str) -> bool:
        try:
            # Create message
            msg = MIMEMultipart()
            msg['From'] = f"{self.sender_name} <{self.sender_email}>"
            msg['To'] = prospect.email
            msg['Subject'] = content['subject']
            
            # Add tracking pixel
            tracking_pixel = f'<img src="https://{self.tracking_domain}/track/{history_id}/open.png" width="1" height="1" alt="">'
            
            # Make sure body is not None
            body = content.get('body', '')
            if not body:
                body = "Thank you for your interest in our insurance solutions. We'll be in touch soon with more information tailored to your needs."
            
            # Add tracking links (in a real implementation)
            body_with_tracking = body + tracking_pixel
            
            msg.attach(MIMEText(body_with_tracking, 'html'))
            
            # For development, just log the email
            logger.info(f"Email sent to {prospect.email}")
            logger.info(f"Subject: {content['subject']}")
            logger.info(f"Body:\n{body}")
            
            # Uncomment to actually send emails in production
            """
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.smtp_username, self.smtp_password)
                server.send_message(msg)
            """
            
            return True
        except Exception as e:
            logger.error(f"Email sending error: {str(e)}")
            return False

# ----- Call Service -----
class CallService:
    def __init__(self):
        self.api_key = os.getenv("CALL_API_KEY", "")
        self.api_url = os.getenv("CALL_API_URL", "https://api.callservice.com")
        self.caller_id = os.getenv("CALLER_ID", "")
    
    def schedule_call(self, prospect: Prospect, script: Dict[str, str], history_id: str) -> bool:
        try:
            # In a real implementation, you'd call an API to schedule a call
            
            logger.info(f"Call scheduled to {prospect.phone}")
            logger.info(f"Script:\n{json.dumps(script, indent=2)}")
            
            # Uncomment to actually schedule calls in production
            """
            call_data = {
                "to": prospect.phone,
                "caller_id": self.caller_id,
                "contact_name": prospect.contact_name,
                "company_name": prospect.company_name,
                "script": script,
                "callback_url": f"https://api.yourapp.com/calls/{history_id}/status"
            }
            
            response = requests.post(
                f"{self.api_url}/schedule",
                json=call_data,
                headers={"Authorization": f"Bearer {self.api_key}"}
            )
            response.raise_for_status()
            """
            
            return True
        except Exception as e:
            logger.error(f"Call scheduling error: {str(e)}")
            return False

# ----- Workflow Engine -----
class OutreachWorkflow:
    def __init__(self):
        self.db = ProspectDatabase()
        self.generator = OutreachGenerator()
        self.email_service = EmailService()
        self.call_service = CallService()
    
    def process_prospect(self, prospect: Prospect, channel: Optional[OutreachChannel] = None):
        """Process a prospect through the appropriate outreach channel(s)."""
        if not channel:
            channel = prospect.preferred_channel
        
        logger.info(f"Processing prospect: {prospect.company_name} via {channel}")
        
        # Get prospect history
        history = self.db.get_prospect_history(prospect.id)
        
        # Process based on channel
        if channel == OutreachChannel.EMAIL or channel == OutreachChannel.BOTH:
            self._process_email(prospect, history)
        
        if channel == OutreachChannel.CALL or channel == OutreachChannel.BOTH:
            self._process_call(prospect, history)
        
        # Generate engagement advice regardless of channel
        advice = self.generator.generate_engagement_advice(prospect, history)
        logger.info(f"Engagement advice for {prospect.company_name}:\n{advice}")
        
        return advice


    def _process_email(self, prospect: Prospect, history: List[OutreachHistory]):
        """Send appropriate email based on prospect's engagement history."""
        # Create outreach history record first
        outreach = OutreachHistory(
            prospect_id=prospect.id,
            channel=OutreachChannel.EMAIL,
            content={},
            status=OutreachStatus.PENDING
        )
        history_id = self.db.add_history(outreach)
        
        try:
            # Generate email content
            if any(h.status == OutreachStatus.RESPONDED for h in history):
                content = self.generator.generate_follow_up(prospect, history)
            else:
                content = self.generator.generate_email(prospect)
            
            # Update history with generated content
            self.db.update_history(history_id, {
                "content": content,
                "status": OutreachStatus.SENT
            })
            
            # Send email
            success = self.email_service.send_email(prospect, content, history_id)
            if not success:
                self.db.update_history(history_id, {"status": OutreachStatus.FAILED})
            
            # Update engagement level
            if prospect.engagement_level == EngagementLevel.NONE:
                self.db.update_prospect(prospect.id, {"engagement_level": EngagementLevel.LOW})
        
        except Exception as e:
            logger.error(f"Email processing failed: {str(e)}")
            self.db.update_history(history_id, {"status": OutreachStatus.FAILED})

    def _process_call(self, prospect: Prospect, history: List[OutreachHistory]):
        """Handle phone outreach based on prospect's engagement history."""
        if not prospect.phone:
            logger.warning(f"No phone number for {prospect.company_name}")
            return
        
        # Create outreach history record
        outreach = OutreachHistory(
            prospect_id=prospect.id,
            channel=OutreachChannel.CALL,
            content={},
            status=OutreachStatus.PENDING
        )
        history_id = self.db.add_history(outreach)
        
        try:
            # Generate call script
            script = self.generator.generate_call_script(prospect)
            
            # Update history with generated content
            self.db.update_history(history_id, {
                "content": script,
                "status": OutreachStatus.SENT
            })
            
            # Schedule call
            success = self.call_service.schedule_call(prospect, script, history_id)
            if not success:
                self.db.update_history(history_id, {"status": OutreachStatus.FAILED})
            
            # Update engagement level
            new_level = min(EngagementLevel.HIGH, EngagementLevel(prospect.engagement_level.value + 1))
            self.db.update_prospect(prospect.id, {"engagement_level": new_level})
        
        except Exception as e:
            logger.error(f"Call processing failed: {str(e)}")
            self.db.update_history(history_id, {"status": OutreachStatus.FAILED})

# ----- API Endpoints -----
app = FastAPI()

@app.post("/prospects/")
async def create_prospect(prospect: Prospect, background_tasks: BackgroundTasks):
    db = ProspectDatabase()
    prospect_id = db.add_prospect(prospect)
    workflow = OutreachWorkflow()
    
    background_tasks.add_task(
        workflow.process_prospect,
        prospect=prospect
    )
    
    return JSONResponse({
        "message": "Prospect added and processing started",
        "prospect_id": prospect_id
    })

@app.get("/prospects/{prospect_id}")
async def get_prospect(prospect_id: str):
    db = ProspectDatabase()
    prospect = db.get_prospect(prospect_id)
    if not prospect:
        raise HTTPException(status_code=404, detail="Prospect not found")
    return prospect

@app.get("/prospects/{prospect_id}/history")
async def get_prospect_history(prospect_id: str):
    db = ProspectDatabase()
    history = db.get_prospect_history(prospect_id)
    return history

# ----- Execution Block -----
def main():
    # Initialize sample prospect
    db = ProspectDatabase()
    workflow = OutreachWorkflow()
    
    sample_prospect = Prospect(
        company_name="TechSecure Inc",
        industry=IndustryType.TECH,
        contact_name="Sarah Johnson",
        email="s.johnson@techsecure.com",
        phone="+1234567890",
        notes="Startup specializing in blockchain security solutions"
    )
    
    # Add and process prospect
    prospect_id = db.add_prospect(sample_prospect)
    logger.info(f"Processing sample prospect: {prospect_id}")
    
    # Run outreach workflow
    advice = workflow.process_prospect(sample_prospect)
    logger.info(f"Generated Engagement Advice:\n{advice}")
    
    # Start API server
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

if __name__ == "__main__":
    main()
   