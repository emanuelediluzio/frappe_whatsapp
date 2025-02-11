"""Webhook."""
import frappe
import json
import requests
import time

from werkzeug.wrappers import Response
from frappe.integrations.utils import make_post_request
from active_users.utils.api import get_users

settings = frappe.get_doc(
            "WhatsApp Settings", "WhatsApp Settings",
        )
token = settings.get_password("token")

"""Ricavo Token API OpenAi."""
token_api = settings.get_password("token_open_ai")

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

    # Calcola il numero di utenti online
    online_users = get_users()
    numero_utenti_online = len(online_users)

    messages = []
    try:
        messages = data["entry"][0]["changes"][0]["value"].get("messages", [])
    except KeyError:
        messages = data["entry"]["changes"][0]["value"].get("messages", [])

    if messages:
        for message in messages:
            message_type = message['type']
        if numero_utenti_online >= 1:
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
                response = requests.get(f'https://graph.facebook.com/v17.0/{media_id}/', headers=headers)
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

        elif numero_utenti_online == 0: ##controllo che non ci siano utenti online
                            
                            data = {
                               "messaging_product": "whatsapp",
                               "to": ("+" + str(message['from'])),
                               "type": "text",
                               "preview_url": True,
                               "body": get_ai_response(message['text']['body']) ##ottengo la risposta dal messaggio in entrata dall'intelligenza artificiale
                            }

                            headers = {
                               "authorization": f"Bearer {token}",
                               "content-type": "application/json"
                            }
                            try:
                              response = make_post_request(
                                f"{settings.url}/{settings.version}/{settings.phone_id}/messages",
                                headers=headers, data=json.dumps(data)
                              )
                              frappe.get_doc({##vado poi a creare il doctype con il messaggio in uscita
                               "doctype": "WhatsApp Message",
                               "type": "Outgoing",
                               "to": ("+" + str(message['from'])),
                               "message": get_ai_response(message),
                               "message_id": response['messages'][0]['id']
                              }).insert(ignore_permissions=True)
                            
                            except Exception as e:
                               res = frappe.flags.integration_request.json()['error']
                               frappe.get_doc({
                                 "doctype": "WhatsApp Notification Log",
                                 "template": "Text Message",
                                 "meta_data": frappe.flags.integration_request.json()
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

def get_ai_response(message):
     api_key = token_api
     endpoint = "https://api.openai.com/v1/chat/completions"
    
     headers = {
         "Content-Type": "application/json",
         "Authorization": "Bearer " + api_key,
     }

     data = {
        "messages": [
            {"role": "system", "content": "Sei un intelligenza artificiale che impersona un operatore di una chat di aiuto della ASCOM Imola, adesso ti fornisco varie info che puoi utilizzare per rispondere alle varie domande (IndirizzoAscom (Ufficio) a ImolaViale Rivalta 640026 ImolaDettagli di contatto 0542 619611* Fax.: 0542 619619 www.confcommercioimo... » Aggiungi il tuo indirizzo e-mail »Apre in 68:44 oreOrari di aperturaLunedi  08:30-12:00 e 14:30-16:30Martedi    08:30-12:00 e 14:30-16:30Mercoledi  08:30-12:00Giovedi  08:30-12:00 e 14:30-16:30Venerdi    08:30-12:00Sabato   chiusoDomenica  chiusoAdesso sono le ore 12:46), facendo pero attenzione a comunicare all'interlocutore di essere un intelligenza artificale e che appena un operatore sara' online ricevera' assistenza da quest'ultimo."},
            {"role": "user", "content": message}
        ],
        "model": "gpt-3.5-turbo"  # Specifica il modello da utilizzare
    }


     response = requests.post(endpoint, headers=headers, json=data)

     if response.status_code == 200:
         choices = response.json()["choices"]
         return choices[0]["message"]["content"]
     else:
       error_message = "Si è verificato un errore nell'interazione con l'AI."
       if response.text:
          try:
             error_response = json.loads(response.text)
             if "error" in error_response and "message" in error_response["error"]:
                 error_message = error_response["error"]["message"]
          except Exception as e:
            pass
     return error_message
