import smtplib
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime

# SMTP конфигурация из переменных окружения
SMTP_HOST = os.getenv('SMTP_HOST', 'smtp.gmail.com')
SMTP_PORT = int(os.getenv('SMTP_PORT', '587'))
SMTP_USER = os.getenv('SMTP_USER', '')
SMTP_PASSWORD = os.getenv('SMTP_PASSWORD', '')
FROM_EMAIL = os.getenv('FROM_EMAIL', SMTP_USER)
FROM_NAME = os.getenv('FROM_NAME', 'GlobalDent RAG System')

def send_email(to_email, subject, html_body):
    """
    Отправляет email через SMTP
    
    Args:
        to_email: email получателя
        subject: тема письма
        html_body: HTML-содержимое письма
    
    Returns:
        True если успешно, False если ошибка
    """
    if not SMTP_USER or not SMTP_PASSWORD:
        print("❌ SMTP credentials not configured")
        return False
    
    try:
        # Создаем сообщение
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = f"{FROM_NAME} <{FROM_EMAIL}>"
        msg['To'] = to_email
        
        # Добавляем HTML-контент
        html_part = MIMEText(html_body, 'html', 'utf-8')
        msg.attach(html_part)
        
        # Отправляем через SMTP
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.send_message(msg)
        
        print(f"✅ Email sent to {to_email}")
        return True
    except Exception as e:
        print(f"❌ Error sending email: {e}")
        return False

def send_verification_email(to_email, code):
    """
    Отправляет письмо с кодом верификации
    
    Args:
        to_email: email получателя
        code: 6-значный код верификации
    
    Returns:
        True если успешно, False если ошибка
    """
    subject = "Подтверждение регистрации - GlobalDent RAG"
    
    html_body = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            body {{
                font-family: 'Open Sans', Arial, sans-serif;
                background-color: #f7f7f7;
                margin: 0;
                padding: 0;
            }}
            .container {{
                max-width: 600px;
                margin: 40px auto;
                background-color: #ffffff;
                border-radius: 12px;
                overflow: hidden;
                box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
            }}
            .header {{
                background: linear-gradient(135deg, #bfab8a 0%, #d4c4a8 100%);
                padding: 30px;
                text-align: center;
                color: #ffffff;
            }}
            .header h1 {{
                margin: 0;
                font-size: 24px;
                font-weight: 600;
            }}
            .content {{
                padding: 40px 30px;
            }}
            .code-box {{
                background-color: #f7f7f7;
                border: 2px solid #bfab8a;
                border-radius: 8px;
                padding: 20px;
                text-align: center;
                margin: 30px 0;
            }}
            .code {{
                font-size: 32px;
                font-weight: 700;
                color: #2d2d2d;
                letter-spacing: 8px;
                font-family: 'Courier New', monospace;
            }}
            .message {{
                color: #6f6f6f;
                line-height: 1.6;
                margin-bottom: 20px;
            }}
            .footer {{
                background-color: #f7f7f7;
                padding: 20px;
                text-align: center;
                color: #6f6f6f;
                font-size: 12px;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>Подтверждение регистрации</h1>
            </div>
            <div class="content">
                <p class="message">
                    Здравствуйте!<br><br>
                    Спасибо за регистрацию в GlobalDent RAG System. 
                    Для завершения регистрации введите следующий код:
                </p>
                <div class="code-box">
                    <div class="code">{code}</div>
                </div>
                <p class="message">
                    Код действителен в течение 15 минут.<br>
                    Если вы не регистрировались в нашей системе, просто проигнорируйте это письмо.
                </p>
            </div>
            <div class="footer">
                <p>GlobalDent RAG System © {datetime.now().year}</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    return send_email(to_email, subject, html_body)

def send_two_fa_email(to_email, code):
    """
    Отправляет письмо с 2FA кодом для доступа в админ-панель
    
    Args:
        to_email: email получателя
        code: 6-значный 2FA код
    
    Returns:
        True если успешно, False если ошибка
    """
    subject = "Код доступа в админ-панель - GlobalDent RAG"
    
    html_body = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            body {{
                font-family: 'Open Sans', Arial, sans-serif;
                background-color: #f7f7f7;
                margin: 0;
                padding: 0;
            }}
            .container {{
                max-width: 600px;
                margin: 40px auto;
                background-color: #ffffff;
                border-radius: 12px;
                overflow: hidden;
                box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
            }}
            .header {{
                background: linear-gradient(135deg, #bfab8a 0%, #d4c4a8 100%);
                padding: 30px;
                text-align: center;
                color: #ffffff;
            }}
            .header h1 {{
                margin: 0;
                font-size: 24px;
                font-weight: 600;
            }}
            .content {{
                padding: 40px 30px;
            }}
            .code-box {{
                background-color: #f7f7f7;
                border: 2px solid #bfab8a;
                border-radius: 8px;
                padding: 20px;
                text-align: center;
                margin: 30px 0;
            }}
            .code {{
                font-size: 32px;
                font-weight: 700;
                color: #2d2d2d;
                letter-spacing: 8px;
                font-family: 'Courier New', monospace;
            }}
            .message {{
                color: #6f6f6f;
                line-height: 1.6;
                margin-bottom: 20px;
            }}
            .warning {{
                background-color: #fff3cd;
                border-left: 4px solid #ffc107;
                padding: 12px;
                margin: 20px 0;
                color: #856404;
            }}
            .footer {{
                background-color: #f7f7f7;
                padding: 20px;
                text-align: center;
                color: #6f6f6f;
                font-size: 12px;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>Код доступа в админ-панель</h1>
            </div>
            <div class="content">
                <p class="message">
                    Здравствуйте!<br><br>
                    Вы запросили доступ в админ-панель GlobalDent RAG System. 
                    Введите следующий код для входа:
                </p>
                <div class="code-box">
                    <div class="code">{code}</div>
                </div>
                <div class="warning">
                    <strong>Важно!</strong> Код действителен в течение 5 минут.
                </div>
                <p class="message">
                    Если вы не запрашивали доступ в админ-панель, немедленно измените пароль вашей учетной записи.
                </p>
            </div>
            <div class="footer">
                <p>GlobalDent RAG System © {datetime.now().year}</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    return send_email(to_email, subject, html_body)

def send_password_reset_email(to_email, code):
    """
    Отправляет письмо с кодом восстановления пароля
    
    Args:
        to_email: email получателя
        code: 6-значный код восстановления
    
    Returns:
        True если успешно, False если ошибка
    """
    subject = "Восстановление пароля - GlobalDent RAG"
    
    html_body = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            body {{
                font-family: 'Open Sans', Arial, sans-serif;
                background-color: #f7f7f7;
                margin: 0;
                padding: 0;
            }}
            .container {{
                max-width: 600px;
                margin: 40px auto;
                background-color: #ffffff;
                border-radius: 12px;
                overflow: hidden;
                box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
            }}
            .header {{
                background: linear-gradient(135deg, #bfab8a 0%, #d4c4a8 100%);
                padding: 30px;
                text-align: center;
                color: #ffffff;
            }}
            .header h1 {{
                margin: 0;
                font-size: 24px;
                font-weight: 600;
            }}
            .content {{
                padding: 40px 30px;
            }}
            .code-box {{
                background-color: #f7f7f7;
                border: 2px solid #bfab8a;
                border-radius: 8px;
                padding: 20px;
                text-align: center;
                margin: 30px 0;
            }}
            .code {{
                font-size: 32px;
                font-weight: 700;
                color: #2d2d2d;
                letter-spacing: 8px;
                font-family: 'Courier New', monospace;
            }}
            .message {{
                color: #6f6f6f;
                line-height: 1.6;
                margin-bottom: 20px;
            }}
            .warning {{
                background-color: #fff3cd;
                border-left: 4px solid #ffc107;
                padding: 12px;
                margin: 20px 0;
                color: #856404;
            }}
            .footer {{
                background-color: #f7f7f7;
                padding: 20px;
                text-align: center;
                color: #6f6f6f;
                font-size: 12px;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>Восстановление пароля</h1>
            </div>
            <div class="content">
                <p class="message">
                    Здравствуйте!<br><br>
                    Вы запросили восстановление пароля в GlobalDent RAG System. 
                    Введите следующий код для продолжения:
                </p>
                <div class="code-box">
                    <div class="code">{code}</div>
                </div>
                <div class="warning">
                    <strong>Важно!</strong> Код действителен в течение 15 минут.
                </div>
                <p class="message">
                    Если вы не запрашивали восстановление пароля, просто проигнорируйте это письмо.
                </p>
            </div>
            <div class="footer">
                <p>GlobalDent RAG System © {datetime.now().year}</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    return send_email(to_email, subject, html_body)

if __name__ == '__main__':
    # Тест отправки email
    print("Testing email service...")
    print(f"SMTP configured: {bool(SMTP_USER and SMTP_PASSWORD)}")
    
    if SMTP_USER and SMTP_PASSWORD:
        test_email = input("Enter test email address: ")
        print("\nSending verification email...")
        if send_verification_email(test_email, "123456"):
            print("✅ Verification email sent successfully")
        else:
            print("❌ Failed to send verification email")
    else:
        print("⚠️ SMTP not configured. Set SMTP_USER and SMTP_PASSWORD in .env")
