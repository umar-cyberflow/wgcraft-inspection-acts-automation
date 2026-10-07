"""Browser wrapper: waiting for elements, clicking, typing, login."""
import time

from selenium import webdriver
from selenium.common.exceptions import (
    ElementClickInterceptedException,
    ElementNotInteractableException,
    StaleElementReferenceException,
    TimeoutException,
)
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys


class Browser:
    def __init__(self, cfg: dict, selectors: dict):
        self.cfg = cfg
        self.sel = selectors
        t = cfg["timeouts"]
        self.page_timeout = t["page"]
        self.element_timeout = t["element"]
        self.pause = t["after_click"]
        self.step_by_step = cfg.get("step_by_step", False)
        self._creds = None

        if cfg.get("browser", "chrome").lower() == "edge":
            opts = webdriver.EdgeOptions()
            opts.add_argument("--start-maximized")
            self.driver = webdriver.Edge(options=opts)
        else:
            opts = webdriver.ChromeOptions()
            opts.add_argument("--start-maximized")
            self.driver = webdriver.Chrome(options=opts)

    # ---------- helpers ----------
    def xp(self, key: str, **kw) -> str:
        """XPath from selectors.json, with {placeholders} filled in."""
        return self.sel[key].format(**kw)

    def _step(self, desc: str):
        print(f"    -> {desc}")
        if self.step_by_step:
            input("      [Enter] to continue...")

    def find(self, xpath: str, timeout=None, last=False):
        """Wait for a visible element. last=True returns the one in the top-most dialog."""
        end = time.time() + (timeout or self.element_timeout)
        while time.time() < end:
            try:
                els = [e for e in self.driver.find_elements(By.XPATH, xpath) if e.is_displayed()]
                if els:
                    return els[-1] if last else els[0]
            except StaleElementReferenceException:
                pass
            time.sleep(0.3)
        raise TimeoutException(f"Element not found: {xpath}")

    def exists(self, xpath: str, timeout=3, last=False) -> bool:
        try:
            self.find(xpath, timeout, last)
            return True
        except TimeoutException:
            return False

    def click(self, xpath: str, desc: str, timeout=None, last=False):
        self._step(desc)
        el = self.find(xpath, timeout, last)
        try:
            el.click()
        except (ElementClickInterceptedException, ElementNotInteractableException):
            self.driver.execute_script("arguments[0].click();", el)
        time.sleep(self.pause)

    def type(self, xpath: str, text: str, desc: str, last=False):
        self._step(desc)
        el = self.find(xpath, last=last)
        try:
            el.click()
        except (ElementClickInterceptedException, ElementNotInteractableException):
            # a placeholder label may cover the field - focus it via JavaScript
            self.driver.execute_script("arguments[0].focus();", el)
        el.send_keys(Keys.CONTROL, "a")
        el.send_keys(Keys.DELETE)
        el.send_keys(text)
        time.sleep(self.pause)

    def paste(self, xpath: str, text: str, desc: str):
        """Set a value as if pasted (for inputs that filter typed characters)."""
        self._step(desc)
        el = self.find(xpath)
        self.driver.execute_script(
            """
            const el = arguments[0], val = arguments[1];
            el.focus();
            const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set;
            setter.call(el, val);
            el.dispatchEvent(new Event('input', {bubbles: true}));
            el.dispatchEvent(new Event('change', {bubbles: true}));
            el.dispatchEvent(new Event('blur', {bubbles: true}));
            """,
            el, text,
        )
        time.sleep(self.pause)
        actual = el.get_attribute("value")
        if actual != text:
            raise RuntimeError(f"Field received '{actual}' instead of '{text}'")

    def set_checkbox(self, xpath: str, value: bool, desc: str):
        el = self.find(xpath)
        if el.is_selected() != value:
            self._step(desc)
            try:
                el.click()
            except (ElementClickInterceptedException, ElementNotInteractableException):
                self.driver.execute_script("arguments[0].click();", el)
            time.sleep(self.pause)

    def press_escape(self, times=1):
        for _ in range(times):
            self.driver.switch_to.active_element.send_keys(Keys.ESCAPE)
            time.sleep(0.5)

    def save_page(self, path: str):
        """Save the page HTML - useful for fixing selectors."""
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(self.driver.page_source)
        except Exception:
            pass

    def screenshot(self, path: str):
        try:
            self.driver.save_screenshot(path)
        except Exception:
            pass

    def reload_home(self):
        self.driver.get(self.cfg["url"])
        time.sleep(self.pause * 2)

    def quit(self):
        self.driver.quit()

    # ---------- login ----------
    def login(self, username: str, password: str):
        """Log in without any manual steps."""
        self._creds = (username, password)
        print("Logging in...")
        saved, self.step_by_step = self.step_by_step, False
        try:
            self.driver.get(self.cfg["url"])
            # a fresh browser profile does not remember the UI language - switch to Russian
            if self.exists(self.xp("lang_ru"), timeout=5):
                self.click(self.xp("lang_ru"), "Language: ru")
            self.type(self.xp("login_input"), username, "Enter login")
            self.type(self.xp("password_input"), password, "Enter password")
            self.click(self.xp("login_button"), "Login button")

            # wait for the login form to disappear
            end = time.time() + self.page_timeout
            while time.time() < end and self.exists(self.xp("login_input"), timeout=1):
                time.sleep(1)
            if self.exists(self.xp("login_input"), timeout=1):
                raise TimeoutException("Login failed - check the credentials in .env")

            self.find(self.xp("menu_acts"), timeout=self.page_timeout)
        finally:
            self.step_by_step = saved
        print("Logged in.\n")

    def ensure_logged_in(self):
        """If the session expired and the login page is back, log in again."""
        if self.exists(self.xp("login_input"), timeout=2):
            print("    ! Session expired - logging in again")
            self.login(*self._creds)
