import smtplib
import time
import os
import random
import uuid
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from rich.console import Console
from rich.progress import Progress, BarColumn, TextColumn, TimeRemainingColumn, SpinnerColumn
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
import threading

# === CONFIGURATION ===
EMAILS_FILE = "nath.txt"
LINKS_FILE = "links (1).txt"
LETTER_FILE = "letter (1).html"
SUBJECT_FILE = "subject.txt"
SENDERNAME_FILE = "sendername.txt"
SMTP_FILE = "smtp.txt"

# === SETUP ===
console = Console()
emails_sent = 0
success = 0
fail = 0
lock = threading.Lock()
change_interval = random.choice([3, 5, 7, 10])  # Initial random interval
emails_since_last_change = 0
current_sender_name = None
current_subject = None
current_smtp_config = None

# === UTILITAIRES ===
def lire_fichier_liste(path):
    with open(path, "r", encoding="utf-8", errors='ignore') as f:
        return [line.strip() for line in f if line.strip()]

def lire_fichier_simple(path):
    with open(path, "r", encoding="utf-8", errors='ignore') as f:
        return f.read().strip()

def lire_smtp_config(path):
    configs = []
    with open(path, "r", encoding="utf-8", errors='ignore') as f:
        for line in f:
            if line.strip():
                try:
                    server, port, user, password = line.strip().split(':')
                    configs.append({
                        'server': server,
                        'port': int(port),
                        'user': user,
                        'password': password
                    })
                except ValueError:
                    console.print(f"[red]Erreur : Ligne mal formatée dans {path}: {line.strip()}[/red]")
    return configs

def envoyer_email(smtp_config, mail_from, sender_name, subject, recipient, content, link):
    try:
        msg = MIMEMultipart()
        msg["From"] = f"{sender_name} <{mail_from}>"
        msg["To"] = recipient
        msg["Subject"] = subject
        msg.add_header("X-Mailer", "Outlook 16.0")
        msg.add_header("List-Unsubscribe", f"<{link}>")
        msg.add_header("Message-ID", f"<{uuid.uuid4()}@{mail_from.split('@')[-1]}>")

        content += f"<!-- {random.randint(1000,9999)} -->"
        msg.attach(MIMEText(content, "html", "utf-8"))

        with smtplib.SMTP(smtp_config['server'], smtp_config['port']) as server:
            server.starttls()
            server.login(smtp_config['user'], smtp_config['password'])
            server.sendmail(mail_from, recipient, msg.as_string())
        return True, smtp_config
    except Exception as e:
        console.print(f"[red]Erreur avec {smtp_config['server']}:{smtp_config['port']}: {e}[/red]")
        return False, smtp_config

def traiter_email(nom_prenom, email, adresse, liens, sujets, noms, smtp_configs, html_template, total, speed, progress, task_id):
    global emails_sent, success, fail, emails_since_last_change, change_interval, current_sender_name, current_subject, current_smtp_config

    with lock:
        # Increment the counter for emails sent since last change
        emails_since_last_change += 1
        # Check if we need to change sender_name, subject, and smtp_config
        if emails_since_last_change >= change_interval:
            current_sender_name = random.choice(noms)
            current_subject = random.choice(sujets)
            current_smtp_config = random.choice(smtp_configs)
            emails_since_last_change = 0  # Reset counter
            change_interval = random.choice([3, 5, 7, 10])  # Choose new random interval
            console.print(f"[bold cyan]Changement : Sender = {current_sender_name}, Subject = {current_subject}, SMTP = {current_smtp_config['server']}:{current_smtp_config['port']}, Mail = {current_smtp_config['user']}, Prochain changement après {change_interval} emails[/bold cyan]")

        sender_name = current_sender_name
        subject = current_subject
        initial_smtp_config = current_smtp_config
        mail_from = initial_smtp_config['user']  # Use the user field as the sender email

    link = random.choice(liens)
    html = html_template.replace("{LINK}", link).replace("{ADDRESS}", adresse).replace("{NOM_PRENOM}", nom_prenom)

    # Try all SMTP configurations until one succeeds or all fail
    smtp_configs_to_try = smtp_configs.copy()  # Create a copy to avoid modifying the original
    random.shuffle(smtp_configs_to_try)  # Randomize to avoid always trying the same order
    success_flag = False
    used_smtp_config = None

    for smtp_config in smtp_configs_to_try:
        ok, used_smtp_config = envoyer_email(smtp_config, smtp_config['user'], sender_name, subject, email, html, link)
        if ok:
            success_flag = True
            break  # Exit the loop on success
        time.sleep(1)  # Brief delay between retries to avoid overwhelming servers

    with lock:
        emails_sent += 1
        if success_flag:
            success += 1
            with open("sent.txt", "a", encoding="utf-8") as f:
                f.write(email + "\n")
        else:
            fail += 1
            with open("failed.txt", "a", encoding="utf-8") as f:
                f.write(email + "\n")

        with open("log.txt", "a", encoding="utf-8") as log:
            log.write(f"{datetime.now()} | {email} | {'OK' if success_flag else 'FAIL'}\n")

        console.print(
            f"[bold {'green' if success_flag else 'red'}]{'✔' if success_flag else '✘'} {email}[/bold {'green' if success_flag else 'red'}] — "
            f"[blue]{link}[/blue] — "
            f"[magenta]{used_smtp_config['user']}[/magenta] — "
            f"[yellow]{emails_sent}/{total}[/yellow] "
            f"({success} ✔ / {fail} ✘)"
        )

        progress.update(task_id, completed=emails_sent)

def main():
    with open(EMAILS_FILE, "r", encoding="utf-8") as f:
        destinataires = []
        for i, line in enumerate(f, 1):
            email = line.strip()
            if email:
                destinataires.append(("", email, ""))  # Nom et Adresse vides

    liens = lire_fichier_liste(LINKS_FILE)
    sujets = lire_fichier_liste(SUBJECT_FILE)
    noms = lire_fichier_liste(SENDERNAME_FILE)
    smtp_configs = lire_smtp_config(SMTP_FILE)
    html_template = lire_fichier_simple(LETTER_FILE)

    # Initialize sender_name, subject, and smtp_config
    global current_sender_name, current_subject, current_smtp_config
    current_sender_name = random.choice(noms)
    current_subject = random.choice(sujets)
    current_smtp_config = random.choice(smtp_configs)
    console.print(f"[bold cyan]Initial : Sender = {current_sender_name}, Subject = {current_subject}, SMTP = {current_smtp_config['server']}:{current_smtp_config['port']}, Mail = {current_smtp_config['user']}, Premier changement après {change_interval} emails[/bold cyan]")

    try:
        speed = int(input("✉️ Emails par seconde ? (ex: 3) : "))
    except:
        speed = 1

    if not destinataires:
        console.print("❌ Aucun email à traiter (fichier vide).", style="bold red")
        return

    if not smtp_configs:
        console.print("❌ Aucun SMTP configuré (fichier vide ou mal formaté).", style="bold red")
        return

    total = len(destinataires)
    console.print(f"✉️ {total} emails prêts à être envoyés.\n", style="bold green")

    progress = Progress(
        SpinnerColumn(),
        TextColumn("➤ Envoi..."),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TimeRemainingColumn(),
        console=console,
        transient=False
    )
    task_id = progress.add_task("Progression", total=total)

    with progress:
        with ThreadPoolExecutor(max_workers=speed) as executor:
            for nom_prenom, email, adresse in destinataires:
                executor.submit(traiter_email, nom_prenom, email, adresse, liens, sujets, noms, smtp_configs, html_template, total, speed, progress, task_id)

            while emails_sent < total:
                time.sleep(0.1)

    console.print("✅ Campagne terminée avec succès !", style="bold green")

if __name__ == "__main__":
    main()