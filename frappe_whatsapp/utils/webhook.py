"""Webhook."""
import frappe
import json
import requests
import time
from frappe.sessions import get_all_active_sessions

from werkzeug.wrappers import Response

# Ottengo la lista degli utenti online
online_users = [session.user for session in get_all_active_sessions()]

settings = frappe.get_doc(
            "WhatsApp Settings", "WhatsApp Settings",
        )
token = settings.get_password("token")

@frappe.whitelist(allow_guest=True)
def webhook():
    """Meta webhook."""
    if frappe.request.method == "GET":
        return get()
    return post(token)

def get():
    """Get."""
    hub_challenge = frappe.form_dict.get("hub.challenge")
    webhook_verify_token = frappe.db.get_single_value(
        "Whatsapp Settings", "webhook_verify_token"
    )

    if frappe.form_dict.get("hub.verify_token") != webhook_verify_token:
        frappe.throw("Verify token does not match")

    return Response(hub_challenge, status=200)


def post(token):
    """Post."""
    data = frappe.local.form_dict
    frappe.get_doc({
        "doctype": "WhatsApp Notification Log",
        "template": "Webhook",
        "meta_data": json.dumps(data)
    }).insert(ignore_permissions=True)

    messages = []
    try:
        messages = data["entry"][0]["changes"][0]["value"].get("messages", [])
    except KeyError:
        messages = data["entry"]["changes"][0]["value"].get("messages", [])

    if messages:
        for message in messages:
            message_type = message['type']
            if message_type == 'text':
                frappe.get_doc({
                    "doctype": "WhatsApp Message",
                    "type": "Incoming",
                    "from": customer(message),
                    "message": message['text']['body']
                }).insert(ignore_permissions=True)

            elif message_type in ["image", "audio", "video", "document"]:
                media_id = message[message_type]["id"]
                headers = {
                    'Authorization': 'Bearer ' + token 

                }
                response = requests.get(f'https://graph.facebook.com/v16.0/{media_id}/', headers=headers)
                
                if response.status_code == 200:
                    media_data = response.json()
                    media_url = media_data.get("url")
                    mime_type = media_data.get("mime_type")
                    file_extension = mime_type.split('/')[1]



                    media_response = requests.get(media_url, headers=headers)
                    if media_response.status_code == 200:
                        file_data = media_response.content



                        file_path = "/opt/bench/frappe-bench/sites/ced.confcommercioimola.cloud/public/files/"
                       
                        file_name = f"{frappe.generate_hash(length=10)}.{file_extension}"
                        file_full_path = file_path + file_name

                        with open(file_full_path, "wb") as file:
                            file.write(file_data)
                       
                        time.sleep(1) 

                        
                        frappe.get_doc({
                            "doctype": "WhatsApp Message",
                            "type": "Incoming",
                            "from": customer(message),
                            "message": f"media:{file_name}"
                        }).insert(ignore_permissions=True)
    else:
        changes = None
        try:
            changes = data["entry"][0]["changes"][0]
        except KeyError:
            changes = data["entry"]["changes"][0]
        update_status(changes)
    return

def customer(message):
    if (frappe.db.get_value("Customer", filters={"mobile_no": ("+" + str(message['from']))}, fieldname="customer_name")):
        return frappe.db.get_value("Customer", filters={"mobile_no": ("+" + str(message['from']))}, fieldname="customer_name")

    else:
        return "not registered:" + "+" + str(message['from'])
    

def update_status(data):
    """Update status hook."""
    if data.get("field") == "message_template_status_update":
        update_template_status(data['value'])

    elif data.get("field") == "messages":
        update_message_status(data['value'])


def update_template_status(data):
    """Update template status."""
    frappe.db.sql(
        """UPDATE `tabWhatsApp Templates`
        SET status = %(event)s
        WHERE id = %(message_template_id)s""",
        data
    )

"""Invia una notifica agli utenti online."""
def send_notification_to_users(online_users, message):
    
    for user in online_users:
        # Esempio: Invia una notifica utilizzando frappe.publish_realtime()
        notification_message = f"Nuovo messaggio da {message['from']}: {message['text']['body']}"
        frappe.publish_realtime(event="notification", message=notification_message, user=user)

"""Interagisci con l'AI e ottieni la risposta."""
def get_ai_response(message):
    api_key = "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"
    endpoint = "https://api.openai.com/v1/engines/davinci-codex/completions"
    prompt = "Utente: {}\nAI:".format(message) + ",rispondi a tale domanda fingendo di essere un operatore della ASCOM Imola(puoi cercare informazioni su orari ecc sulla loro pagina), facendo pero attenzione a comunicare all'interlocutore di essere un intelligenza artificale e che appena un operatore sara' online ricevera' assistenza da quest'ultimo"

    headers = {
        "Content-Type": "application/json",
        "Authorization": "Bearer " + api_key,
    }

    data = {
        "prompt": prompt,
        "max_tokens": 150,
    }

    response = requests.post(endpoint, headers=headers, json=data)

    if response.status_code == 200:
        return response.json()["choices"][0]["text"]
    else:
        return "Si è verificato un errore nell'interazione con l'AI."
    

def update_message_status(data):
    """Update message status."""
    id = data['statuses'][0]['id']
    status = data['statuses'][0]['status']
    conversation = data['statuses'][0].get('conversation', {}).get('id')
    name = frappe.db.get_value("WhatsApp Message", filters={"message_id": id})
    doc = frappe.get_doc("WhatsApp Message", name)

    doc.status = status
    if conversation:
        doc.conversation_id = conversation
    doc.save(ignore_permissions=True)

import requests