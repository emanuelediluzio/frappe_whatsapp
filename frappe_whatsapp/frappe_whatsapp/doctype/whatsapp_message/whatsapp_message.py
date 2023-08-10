# Copyright (c) 2023, Shridhar Patil and contributors
# For license information, please see license.txt
import json
import frappe
import time
import requests
from frappe.model.document import Document
from frappe.integrations.utils import make_post_request
from active_users.utils.api import get_users

class WhatsAppMessage(Document):
    """Send whats app messages."""

    def before_insert(self):
        online_users = get_users()
        numero_utenti_online = len(online_users)
        frappe.msgprint(str(numero_utenti_online), indicator="green", alert=True)
        frappe.msgprint(self.get_ai_response("ciao"), indicator="green", alert=True)
        """Send message."""
        if self.type == 'Outgoing' and self.message_type != 'Template':
            if self.attach and not self.attach.startswith("http"):
                link = frappe.utils.get_url() + '/' + self.attach
            else:
                link = self.attach
         
            if self.switch:
                customers = frappe.db.get_list("Customer", filters={"customer_group": self.gruppo}, pluck="customer_name")
                for customer in customers:
                    mobile_no = frappe.db.get_value("Customer", filters={"customer_name": customer}, fieldname="mobile_no")
                    if mobile_no:
                        self.send_message(mobile_no, link)
                        time.sleep(2)

            if self.notifica:
                customers = frappe.db.get_list("Customer", pluck="customer_name")
                for customer in customers:
                    mobile_no = frappe.db.get_value("Customer", filters={"customer_name": customer}, fieldname="mobile_no")
                    if mobile_no:
                        self.notifyAll(mobile_no)
                        time.sleep(2)          
                        
              
            if not self.switch and not self.notifica:
                mobile_no = frappe.db.get_value("Customer", filters={"customer_name": self.a}, fieldname="mobile_no")
                if mobile_no:
                    self.send_message(mobile_no, link)

    def send_message(self, mobile_no, link):
        """Send WhatsApp message to the specified mobile number."""
        data = {
            "messaging_product": "whatsapp",
            "to": self.format_number(mobile_no),
            "type": self.content_type
        }

        if self.content_type in ['document', 'image', 'video']:
                 data[self.content_type.lower()] = {
                    "link": link,
                    "caption": self.message
                }
        elif self.content_type == "text":
                data["text"] = {
                    "preview_url": True,
                    "body": self.message
                }
        elif self.content_type == "audio":
                data[self.content_type.lower()] = {
                    "link": link
                }     

        try:
            self.notify(data)
            self.status = "Success"
        except Exception as e:
            self.status = "Failed"
            frappe.throw(f"Failed to send message: {str(e)}")


    def notify(self, data):
        """Notify."""

        settings = frappe.get_doc(
            "WhatsApp Settings", "WhatsApp Settings",
        )
        token = settings.get_password("token")

        headers = {
            "authorization": f"Bearer {token}",
            "content-type": "application/json"
        }
        try:
            response = make_post_request(
                f"{settings.url}/{settings.version}/{settings.phone_id}/messages",
                headers=headers, data=json.dumps(data)
            )
            self.message_id = response['messages'][0]['id']
            #frappe.msgprint("Message send to " + self.a + "(" +str(self.format_number(frappe.db.get_value("Customer", filters={"customer_name": self.a}, fieldname="mobile_no"))) +")", indicator="green", alert=True)
            

        except Exception as e:
            res = frappe.flags.integration_request.json()['error']
            error_message = res.get('Error', res.get("message"))
            frappe.get_doc({
                "doctype": "WhatsApp Notification Log",
                "template": "Text Message",
                "meta_data": frappe.flags.integration_request.json()
            }).insert(ignore_permissions=True)

            frappe.throw(
                msg=error_message,
                title=res.get("error_user_title", "Error")
            )

    def notifyAll(self, mobile_no):
        """Notify."""

        settings = frappe.get_doc(
            "WhatsApp Settings", "WhatsApp Settings",
        )
        token = settings.get_password("token")

        template = '{ \"messaging_product\": \"whatsapp\", \"to\": \"'+str(mobile_no)+'\", \"type\": \"template\", \"template\": { \"name\": \"'+self.templates+'\", \"language\": { \"code\": \"en_US\" } } }'

        headers = {
            "authorization": f"Bearer {token}",
            "content-type": "application/json"
        }
        try:
            response = make_post_request(
                f"{settings.url}/{settings.version}/{settings.phone_id}/messages",
                headers=headers, data=template
            )
            self.message_id = response['messages'][0]['id']

        except Exception as e:
            res = frappe.flags.integration_request.json()['error']
            error_message = res.get('Error', res.get("message"))
            frappe.get_doc({
                "doctype": "WhatsApp Notification Log",
                "template": "Text Message",
                "meta_data": frappe.flags.integration_request.json()
            }).insert(ignore_permissions=True)

            frappe.throw(
                msg=error_message,
                title=res.get("error_user_title", "Error")
            )

    def format_number(self, number):
        """Format number."""
        if number.startswith("+"):
            number = number[1:len(number)]

        return number
    
    def get_ai_response(self, message):##testing --> da spostare poi sul webhook
     """Interagisci con l'AI e ottieni la risposta."""
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
    
