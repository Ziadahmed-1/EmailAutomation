import base64
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
import os.path


# Define the scopes
SCOPES = ['https://www.googleapis.com/auth/gmail.modify']

def setup_credentials():
    # Create a flow instance using client secrets file
    flow = InstalledAppFlow.from_client_secrets_file(
        'credentials.json', SCOPES)
    
    # Run the flow to get credentials
    creds = flow.run_local_server(port=0)
    
    # Save the credentials for future use
    with open('token.json', 'w') as token:
        token.write(creds.to_json())
        
    print("Authentication completed successfully! token.json has been created.")

# Improved get_message function that handles various email formats
def get_message(service, msg_id):
    msg = service.users().messages().get(userId='me', id=msg_id, format='full').execute()
    
    # Try to get the message content
    try:
        payload = msg['payload']
        
        # Check if the message has a body directly
        if 'body' in payload and payload['body'].get('data'):
            data = payload['body']['data']
            return base64.urlsafe_b64decode(data).decode('utf-8')
        
        # Handle multipart messages
        elif 'parts' in payload:
            for part in payload['parts']:
                if part['mimeType'] == 'text/plain':
                    data = part['body'].get('data')
                    if data:
                        return base64.urlsafe_b64decode(data).decode('utf-8')
                
                # Handle nested multipart messages
                if 'parts' in part:
                    for subpart in part['parts']:
                        if subpart['mimeType'] == 'text/plain':
                            data = subpart['body'].get('data')
                            if data:
                                return base64.urlsafe_b64decode(data).decode('utf-8')
        
        # If we couldn't find text/plain content, try to get snippet
        return msg.get('snippet', '')
    
    except Exception as e:
        print(f"Error processing message {msg_id}: {e}")
        return None


def check_email_content(content):
    # Define important words statically
    important_words = ['invoice', 'urgent', 'contract', 'deadline', 'important', 'review', 'approval']
    
    # Convert content to lowercase for case-insensitive matching
    if content:
        content_lower = content.lower()
        for word in important_words:
            if word in content_lower:
                return True
    return False


def apply_label(service, msg_id, label_name='AI-Filtered'):
    labels = service.users().labels().list(userId='me').execute()['labels']
    label_id = None

    for label in labels:
        if label['name'] == label_name:
            label_id = label['id']
            break
    
    if not label_id:
        label_obj = service.users().labels().create(userId='me', body={'name': label_name, 'labelListVisibility': 'labelShow', 'messageListVisibility': 'show'}).execute()
        label_id = label_obj['id']

    service.users().messages().modify(
        userId='me', id=msg_id,
        body={'addLabelIds': [label_id]}
    ).execute()


if __name__ == '__main__':
    # If token doesn't exist, set up credentials
    if not os.path.exists('token.json'):
        setup_credentials()
    
    # Load credentials and build service
    creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    service = build('gmail', 'v1', credentials=creds)
    
    # Get messages
    results = service.users().messages().list(userId='me', labelIds=['INBOX'], maxResults=10).execute()
    messages = results.get('messages', [])
    
    # Process the messages
    if messages:
        for message in messages:
            msg_id = message['id']
            content = get_message(service, msg_id)
            if check_email_content(content):
                apply_label(service, msg_id)
                print(f"Labeled message {msg_id} as important")
        print(f"Processed {len(messages)} messages")
    else:
        print("No messages found.")