import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pyairtable import Api
from pyairtable.formulas import match
from dotenv import load_dotenv
import logging
import uuid
from datetime import datetime, timedelta
from dateutil import parser
from email.mime.base import MIMEBase
from email import encoders

load_dotenv()
logger = logging.getLogger(__name__)

# Load Airtable Config
AIRTABLE_API_KEY = os.getenv("AIRTABLE_API_KEY")
AIRTABLE_BASE_ID = os.getenv("AIRTABLE_BASE_ID")
AIRTABLE_TABLE_NAME = os.getenv("AIRTABLE_TABLE_NAME", "Appointments")

# Load SMTP Config
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", 587))
SMTP_USERNAME = os.getenv("SMTP_USERNAME")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
CLINIC_NAME = os.getenv("CLINIC_NAME", "QuensultingAI Dental Clinic")
CLINIC_SENDER_EMAIL = os.getenv("CLINIC_SENDER_EMAIL", SMTP_USERNAME)

def save_to_airtable(name: str, phone: str, service: str, date: str, time: str, email: str = None) -> bool:
    """
    Saves the appointment information to Airtable.
    Requires a table with columns: Name, Phone, Service, Date, Time, Email.
    """
    if not AIRTABLE_API_KEY or not AIRTABLE_BASE_ID:
        logger.error("Airtable API Key or Base ID is missing. Check your .env file.")
        # We can still return True to not crash the bot, but we log the error.
        return False

    try:
        api = Api(AIRTABLE_API_KEY)
        table = api.table(AIRTABLE_BASE_ID, AIRTABLE_TABLE_NAME)
        record = {
            "Name": name,
            "Phone": phone,
            "Service": service,
            "Date": date,
            "Time": time,
        }
        if email:
            record["Email"] = email
            
        table.create(record)
        logger.info(f"Successfully saved appointment to Airtable for {name}")
        return True
    except Exception as e:
        logger.error(f"Error saving to Airtable: {e}")
        return False

def check_availability(date: str, time: str) -> bool:
    """
    Checks if an appointment slot is already taken in Airtable.
    Returns True if available, False if already booked.
    """
    if not AIRTABLE_API_KEY or not AIRTABLE_BASE_ID:
        # If no DB configured, just assume it's available for the sake of the assignment demo.
        return True
        
    try:
        api = Api(AIRTABLE_API_KEY)
        table = api.table(AIRTABLE_BASE_ID, AIRTABLE_TABLE_NAME)
        # We look for any record matching both Date and Time
        existing_records = table.all(formula=match({"Date": date, "Time": time}))
        if len(existing_records) > 0:
            logger.info(f"Slot {date} {time} is already booked.")
            return False
        return True
    except Exception as e:
        logger.error(f"Error checking availability: {e}")
        return True # Default to True on error to not block flow

def generate_ics(name: str, service: str, date_str: str, time_str: str) -> str:
    """
    Generates an iCalendar (.ics) string for the appointment.
    """
    try:
        # Try to parse the date and time provided by the AI
        dt_str = f"{date_str} {time_str}"
        start_time = parser.parse(dt_str)
        # Default duration is 1 hour
        end_time = start_time + timedelta(hours=1)
        
        dtstamp = datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')
        dtstart = start_time.strftime('%Y%m%dT%H%M%S')
        dtend = end_time.strftime('%Y%m%dT%H%M%S')
        uid = uuid.uuid4().hex
        
        ics_content = f"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//{CLINIC_NAME}//EN
CALSCALE:GREGORIAN
METHOD:REQUEST
BEGIN:VEVENT
DTSTAMP:{dtstamp}
DTSTART;TZID=Asia/Kolkata:{dtstart}
DTEND;TZID=Asia/Kolkata:{dtend}
SUMMARY:{service} at {CLINIC_NAME}
DESCRIPTION:Dental appointment for {name}
LOCATION:Pune, Maharashtra
UID:{uid}
STATUS:CONFIRMED
SEQUENCE:0
END:VEVENT
END:VCALENDAR"""
        return ics_content
    except Exception as e:
        logger.error(f"Error generating ICS: {e}")
        return None

def send_confirmation_email(patient_email: str, name: str, service: str, date: str, time: str) -> bool:
    """
    Sends a confirmation email to the patient using SMTP.
    """
    if not SMTP_USERNAME or not SMTP_PASSWORD:
        logger.error("SMTP credentials are missing. Check your .env file.")
        return False

    if not patient_email:
        logger.warning("No patient email provided, skipping confirmation email.")
        return False

    subject = f"Appointment Confirmation - {CLINIC_NAME}"
    body = f"""
    Dear {name},
    
    This email confirms your appointment at {CLINIC_NAME}.
    
    Details:
    - Service: {service}
    - Date: {date}
    - Time: {time}
    
    If you need to reschedule or cancel, please contact us. We look forward to seeing you.
    
    Best regards,
    The Team at {CLINIC_NAME}
    """

    msg = MIMEMultipart()
    msg['From'] = f"{CLINIC_NAME} <{CLINIC_SENDER_EMAIL}>"
    msg['To'] = patient_email
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain'))
    
    # Generate and attach Calendar Invite (.ics)
    ics_content = generate_ics(name, service, date, time)
    if ics_content:
        part = MIMEBase('text', 'calendar', method='REQUEST', name='invite.ics')
        part.set_payload(ics_content)
        encoders.encode_base64(part)
        part.add_header('Content-Disposition', 'attachment; filename="invite.ics"')
        part.add_header('Content-class', 'urn:content-classes:calendarmessage')
        msg.attach(part)

    try:
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(SMTP_USERNAME, SMTP_PASSWORD)
        server.send_message(msg)
        server.quit()
        logger.info(f"Successfully sent confirmation email to {patient_email}")
        return True
    except Exception as e:
        logger.error(f"Error sending email: {e}")
        return False
