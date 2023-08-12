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

    settings = frappe.get_doc(
            "WhatsApp Settings", "WhatsApp Settings",
        )
    token = settings.get_password("token")

    """Ricavo Token API OpenAi."""
    token_api = settings.get_password("token_open_ai")

    def before_insert(self):
        """Send message."""
        if self.type == 'Outgoing' and self.message_type != 'Template':
            if self.attach and not self.attach.startswith("http"):
                link = frappe.utils.get_url() + '/' + self.attach
            else:
                link = self.attach


        online_users = get_users()
        numero_utenti_online = len(online_users)
        if numero_utenti_online == 0 and self.type == 'Incoming': 
            data = {
                "messaging_product": "whatsapp",
                "to": self.format_number(self.get_mobile_number(self.from)),
                "type": "text",
                "preview_url": True,
                "body": self.get_ai_response(self.message) ##ottengo la risposta dal messaggio in entrata dall'intelligenza artificiale
                    }

            try:
                self.notify(data)
                self.status = "Success"
            except Exception as e:
                self.status = "Failed"
            frappe.throw(f"Failed to send message: {str(e)}")
         

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
    
    def get_ai_response(self, message):
     api_key = self.token_api
     endpoint = "https://api.openai.com/v1/chat/completions"
    
     headers = {
         "Content-Type": "application/json",
         "Authorization": "Bearer " + api_key,
     }

     data = {
        "messages": [
            {"role": "system", "content": "Sei un intelligenza artificiale che impoersona un operatore di una chat di aiuto della ASCOM Imola, adesso ti fornisco varie info che puoi utilizzare per rispondere alle varie domande (IndirizzoAscom (Ufficio) a ImolaViale Rivalta 640026 ImolaDettagli di contatto 0542 619611* Fax.: 0542 619619 www.confcommercioimo... » Aggiungi il tuo indirizzo e-mail »Apre in 68:44 oreOrari di aperturaLunedi  08:30-12:00 e 14:30-16:30Martedi    08:30-12:00 e 14:30-16:30Mercoledi  08:30-12:00Giovedi  08:30-12:00 e 14:30-16:30Venerdi    08:30-12:00Sabato   chiusoDomenica  chiusoAdesso sono le ore 12:46), facendo pero attenzione a comunicare all'interlocutore di essere un intelligenza artificale e che appena un operatore sara' online ricevera' assistenza da quest'ultimo."},
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
    
    def get_mobile_number(self, customer_name):
     mobile_no = frappe.db.get_value("Customer", filters={"customer_name": customer_name}, fieldname="mobile_no")
     return mobile_no if mobile_no else "not registered"
