"""
WhatsApp Web Bulk Image Sender
Automates sending an image with a caption to multiple contacts via WhatsApp Web.

Requirements:
    pip install selenium webdriver-manager
"""

import csv
import time
import random
import os
import sys

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException,
    NoSuchElementException,
    ElementClickInterceptedException,
)
from webdriver_manager.chrome import ChromeDriverManager

# ─────────────────────────────────────────────
# CONFIGURATION  — edit these before running
# ─────────────────────────────────────────────
IMAGE_PATH = r"C:\path\to\your\image.jpg"   # Absolute path to the image file
CAPTION    = "Hello! Here is your message."  # Caption sent with the image
CSV_FILE   = "contacts.csv"                  # CSV with columns: name, phone
DELAY_MIN  = 7    # Minimum seconds between sends
DELAY_MAX  = 10   # Maximum seconds between sends
QR_TIMEOUT = 60   # Seconds to wait for the user to scan the QR code
# ─────────────────────────────────────────────


def load_contacts(csv_path: str) -> list[dict]:
    """Read contacts from a CSV file. Expected columns: name, phone."""
    if not os.path.exists(csv_path):
        print(f"[ERROR] CSV file not found: {csv_path}")
        sys.exit(1)

    contacts = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            name  = row.get("name",  "").strip()
            phone = row.get("phone", "").strip()
            # Strip any non-digit characters except leading +
            phone_clean = "+" + phone.lstrip("+").replace(" ", "").replace("-", "")
            if phone_clean and phone_clean != "+":
                contacts.append({"name": name, "phone": phone_clean})
    return contacts


def create_driver() -> webdriver.Chrome:
    """Launch Chrome with a persistent profile so WhatsApp session is reused."""
    profile_dir = os.path.join(os.environ["USERPROFILE"], "whatsapp_selenium_profile")

    options = Options()
    options.add_argument(f"--user-data-dir={profile_dir}")
    options.add_argument("--profile-directory=Default")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    # Keep window visible so the user can scan the QR code
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)

    service = Service(ChromeDriverManager().install())
    driver  = webdriver.Chrome(service=service, options=options)
    driver.maximize_window()
    return driver


def wait_for_whatsapp_ready(driver: webdriver.Chrome, timeout: int = QR_TIMEOUT) -> None:
    """
    Open WhatsApp Web and wait until the main chat panel is visible,
    giving the user time to scan the QR code if needed.
    """
    driver.get("https://web.whatsapp.com")
    print(f"[INFO] Waiting up to {timeout}s for WhatsApp Web to load (scan QR if prompted)…")

    try:
        # The side-panel search box is present only after a successful login
        WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located(
                (By.XPATH, '//div[@contenteditable="true"][@data-tab="3"]')
            )
        )
        print("[INFO] WhatsApp Web is ready.")
    except TimeoutException:
        print("[ERROR] Timed out waiting for WhatsApp Web. Did you scan the QR code?")
        driver.quit()
        sys.exit(1)


def open_chat(driver: webdriver.Chrome, phone: str, wait: WebDriverWait) -> None:
    """Navigate directly to the chat for a given phone number."""
    url = f"https://web.whatsapp.com/send?phone={phone}&app_absent=0"
    driver.get(url)

    # Wait for the message input box — confirms the chat loaded
    wait.until(
        EC.presence_of_element_located(
            (By.XPATH, '//div[@contenteditable="true"][@data-tab="10"]')
        )
    )
    # Extra short pause to let the page fully settle
    time.sleep(1.5)


def attach_image(driver: webdriver.Chrome, image_path: str, wait: WebDriverWait) -> None:
    """Click the attachment button and upload the image file."""
    # Click the paperclip / attach button
    attach_btn = wait.until(
        EC.element_to_be_clickable(
            (By.XPATH, '//div[@title="Attach"]')
        )
    )
    attach_btn.click()
    time.sleep(0.8)

    # Click "Photos & Videos" option in the attach menu
    image_option = wait.until(
        EC.presence_of_element_located(
            (By.XPATH, '//input[@accept="image/*,video/mp4,video/3gpp,video/quicktime"]')
        )
    )
    image_option.send_keys(image_path)


def add_caption_and_send(driver: webdriver.Chrome, caption: str, wait: WebDriverWait) -> None:
    """Type the caption in the image preview input and press Send."""
    # Wait for the caption input in the image preview dialog
    caption_box = wait.until(
        EC.presence_of_element_located(
            (By.XPATH, '//div[@contenteditable="true"][@data-tab="10"]')
        )
    )
    caption_box.click()
    caption_box.send_keys(caption)
    time.sleep(0.5)

    # Press Enter to send
    caption_box.send_keys(Keys.ENTER)

    # Wait for the image preview dialog to disappear (message delivered)
    wait.until(
        EC.invisibility_of_element_located(
            (By.XPATH, '//div[@data-animate-photo-viewer="true"]')
        )
    )


def send_image_to_contact(
    driver: webdriver.Chrome,
    contact: dict,
    image_path: str,
    caption: str,
) -> bool:
    """
    Full send flow for a single contact.
    Returns True on success, False on failure.
    """
    phone = contact["phone"]
    name  = contact["name"]
    wait  = WebDriverWait(driver, 20)

    try:
        open_chat(driver, phone, wait)
        attach_image(driver, image_path, wait)

        # Wait for image preview to appear before typing caption
        wait.until(
            EC.presence_of_element_located(
                (By.XPATH, '//div[@data-animate-photo-viewer="true"]')
            )
        )

        add_caption_and_send(driver, caption, wait)
        print(f"[OK]   Sent to {name} ({phone})")
        return True

    except TimeoutException as exc:
        print(f"[FAIL] {name} ({phone}) — Timeout: {exc.msg}")
    except NoSuchElementException as exc:
        print(f"[FAIL] {name} ({phone}) — Element not found: {exc.msg}")
    except ElementClickInterceptedException as exc:
        print(f"[FAIL] {name} ({phone}) — Click intercepted: {exc.msg}")
    except Exception as exc:  # noqa: BLE001
        print(f"[FAIL] {name} ({phone}) — Unexpected error: {exc}")

    return False


def main() -> None:
    # ── Validate image path ──────────────────────────────────────────────────
    abs_image = os.path.abspath(IMAGE_PATH)
    if not os.path.isfile(abs_image):
        print(f"[ERROR] Image not found: {abs_image}")
        sys.exit(1)

    # ── Load contacts ────────────────────────────────────────────────────────
    contacts = load_contacts(CSV_FILE)
    if not contacts:
        print("[ERROR] No valid contacts found in CSV.")
        sys.exit(1)
    print(f"[INFO] Loaded {len(contacts)} contact(s) from '{CSV_FILE}'.")

    # ── Launch browser ───────────────────────────────────────────────────────
    driver = create_driver()

    try:
        wait_for_whatsapp_ready(driver)

        sent_count  = 0
        failed_count = 0

        for i, contact in enumerate(contacts, start=1):
            print(f"\n[{i}/{len(contacts)}] Processing: {contact['name']} ({contact['phone']})")

            success = send_image_to_contact(driver, contact, abs_image, CAPTION)

            if success:
                sent_count += 1
            else:
                failed_count += 1

            # Delay between sends (skip delay after the last contact)
            if i < len(contacts):
                delay = random.uniform(DELAY_MIN, DELAY_MAX)
                print(f"[INFO] Waiting {delay:.1f}s before next send…")
                time.sleep(delay)

    finally:
        print(f"\n{'─'*45}")
        print(f"[DONE] Sent: {sent_count}  |  Failed: {failed_count}")
        driver.quit()
        print("[INFO] Browser closed.")


if __name__ == "__main__":
    main()
