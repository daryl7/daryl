import yaml
import smtplib
from email.mime.text import MIMEText


class Mailer:
    def __init__(self, *args, **kwargs):
        with open('config.yml', 'r') as yml:
            config = yaml.load(yml)
        self.notification_email_to = config['notifycation']['email']['to']
        self.notification_email_from = config['notifycation']['email']['from']
        self.notification_email_subject = config['notifycation']['email']['subject']

    def sendmail(self, message, subject = ""):
        if not self.is_use():
            return
        you = self.notification_email_to
        me = self.notification_email_from
        msg = MIMEText(message)
        msg['Subject'] = self.notification_email_subject if subject == "" else subject
        msg['To'] = you
        msg['From'] = me
        s = smtplib.SMTP()
        s.connect()
        s.sendmail(me, [you], msg.as_string())
        s.close()

    def checkmailer(self):
        s = smtplib.SMTP()
        try:
            s.connect()
            s.close()
        except ConnectionRefusedError:
            return False
        return True

    def is_use(self):
        return not self.notification_email_to == ""
