# gradio_app.py
import gradio as gr
import requests
from datetime import datetime

# FastAPI endpoint configuration
FASTAPI_URL = "http://localhost:8000"

def generate_outreach(company_name, industry, contact_name, email, phone, notes, engagement_level, preferred_channel, objections):
    # Prepare prospect data
    prospect_data = {
        "company_name": company_name,
        "industry": industry,
        "contact_name": contact_name,
        "email": email,
        "phone": phone,
        "notes": notes,
        "engagement_level": engagement_level,
        "preferred_channel": preferred_channel,
        "objections": [obj.strip() for obj in objections.split(",") if obj.strip()]
    }

    try:
        # Create prospect via FastAPI
        response = requests.post(
            f"{FASTAPI_URL}/prospects/",
            json=prospect_data
        )
        response.raise_for_status()
        response_data = response.json()
        prospect_id = response_data["prospect_id"]

        # Get generated outreach content
        history_response = requests.get(
            f"{FASTAPI_URL}/prospects/{prospect_id}/history"
        )
        history = history_response.json()
        
        # Extract latest email content
        email_content = None
        for entry in history:
            if entry.get("channel") == "email" and entry.get("content"):
                email_content = entry["content"]
                break
                
        if not email_content:
            # Retry once after a short delay to give the system time to generate
            import time
            time.sleep(2)
            
            history_response = requests.get(
                f"{FASTAPI_URL}/prospects/{prospect_id}/history"
            )
            history = history_response.json()
            
            for entry in history:
                if entry.get("channel") == "email" and entry.get("content"):
                    email_content = entry["content"]
                    break
        
        # Format output with error handling
        if email_content and isinstance(email_content, dict):
            output = f"Subject: {email_content.get('subject', 'No subject')}\n\n"
            output += email_content.get('body', 'No email body generated')
        else:
            output = "Error: Email content not properly generated. Check the logs for details."
        
        return output

    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        return f"Error generating outreach: {str(e)}\n\nDetails: {error_details}"

# Industry enum values from main.py
industries = ["tech", "finance", "healthcare", "retail", "manufacturing", 
             "education", "construction", "energy", "hospitality", "transportation"]

engagement_levels = ["none", "low", "medium", "high"]
channels = ["email", "call", "both"]

with gr.Blocks(title="Insurance Outreach Generator") as demo:
    gr.Markdown("# AI-Powered Insurance Outreach Generator")
    gr.Markdown("Customize cold emails based on industry and engagement level")
    
    with gr.Row():
        with gr.Column():
            company_name = gr.Textbox(label="Company Name")
            industry = gr.Dropdown(industries, label="Industry", value="tech")
            contact_name = gr.Textbox(label="Contact Name")
            email = gr.Textbox(label="Email")
            phone = gr.Textbox(label="Phone Number")
            notes = gr.Textbox(label="Company Notes", lines=2)
            
        with gr.Column():
            engagement_level = gr.Dropdown(engagement_levels, 
                                         label="Engagement Level", 
                                         value="none")
            preferred_channel = gr.Dropdown(channels, 
                                          label="Preferred Channel", 
                                          value="email")
            objections = gr.Textbox(label="Objections (comma-separated)", 
                                  placeholder="e.g., pricing, coverage, timing")
            
    generate_btn = gr.Button("Generate Outreach", variant="primary")
    
    output = gr.Textbox(label="Generated Email", lines=12, interactive=False)

    generate_btn.click(
        fn=generate_outreach,
        inputs=[company_name, industry, contact_name, email, 
               phone, notes, engagement_level, preferred_channel, objections],
        outputs=output
    )

if __name__ == "__main__":
    demo.launch(server_port=7861, share=True)