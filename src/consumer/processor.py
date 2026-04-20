import os
import logging
from anthropic import Anthropic
from openai import OpenAI
from src.common.db import SessionLocal
from src.database.models import InvoiceJob, JobStatus

logger = logging.getLogger(__name__)

class InvoiceExtractor:
    def __init__(self, provider="anthropic"):
        self.provider = provider
        if provider == "anthropic":
            self.client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        else:
            self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    def extract_data(self, file_content, mime_type):
        """
        Uses LLM Vision to extract data from invoice.
        For simplicity in this skeleton, we assume file_content is base64 encoded for images.
        """
        prompt = """
        Extract the following data from this invoice:
        - Vendor Name
        - Date
        - Total Amount
        - Tax Amount
        - Currency
        - Classification (Income or Expense)
        
        Return the result as a JSON object.
        """
        
        try:
            if self.provider == "anthropic":
                # Implementation for Claude 3.5 Sonnet Vision
                message = self.client.messages.create(
                    model="claude-3-5-sonnet-20240620",
                    max_tokens=1024,
                    messages=[
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "image",
                                    "source": {
                                        "type": "base64",
                                        "media_type": mime_type,
                                        "data": file_content,
                                    },
                                },
                                {"type": "text", "text": prompt}
                            ],
                        }
                    ],
                )
                return message.content[0].text # Needs JSON parsing
            else:
                # Implementation for GPT-4o
                response = self.client.chat.completions.create(
                    model="gpt-4o",
                    messages=[
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": prompt},
                                {
                                    "type": "image_url",
                                    "image_url": {"url": f"data:{mime_type};base64,{file_content}"}
                                },
                            ],
                        }
                    ],
                )
                return response.choices[0].message.content
        except Exception as e:
            logger.error(f"AI Extraction failed: {e}")
            raise e

class JobProcessor:
    def __init__(self):
        self.extractor = InvoiceExtractor(provider=os.getenv("AI_PROVIDER", "anthropic"))

    def process_pending_jobs(self):
        with SessionLocal() as db:
            jobs = db.query(InvoiceJob).filter(InvoiceJob.status == JobStatus.PENDING).all()
            for job in jobs:
                try:
                    logger.info(f"Processing job {job.id} (File: {job.file_name})")
                    job.status = JobStatus.PROCESSING
                    db.commit()

                    # 1. Download file (Implementation omitted for skeleton)
                    # file_data, mime_type = download_from_drive(job.file_id)
                    
                    # 2. Extract Data
                    # result = self.extractor.extract_data(file_data_b64, mime_type)
                    
                    # 3. Update DB
                    job.status = JobStatus.COMPLETED
                    # job.extracted_data = result
                    
                    # 4. Write to Sheets (Implementation omitted)
                    # write_to_sheets(result)
                    
                    db.commit()
                except Exception as e:
                    logger.error(f"Failed to process job {job.id}: {e}")
                    job.status = JobStatus.FAILED
                    job.error_message = str(e)
                    db.commit()

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    processor = JobProcessor()
    processor.process_pending_jobs()
