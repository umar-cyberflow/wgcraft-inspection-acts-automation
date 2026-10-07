"""Inspection acts: accept a new act for processing and confirm its GPS record."""
from selenium.common.exceptions import TimeoutException

OK = "OK"
SKIP = "SKIP"
CHECK = "CHECK"
ERROR = "ERROR"


def open_new_acts(b):
    """Open 'Inspection acts (new)'; expand the menu first if it is collapsed."""
    if not b.exists(b.xp("menu_new_acts"), timeout=2):
        b.click(b.xp("menu_acts"), "Inspection acts menu")
    b.click(b.xp("menu_new_acts"), "Inspection acts (new)")


def search_act(b, act: str) -> bool:
    """Search by act number. Returns True if the act is found."""
    b.find(b.xp("act_input"), timeout=b.page_timeout)  # wait for the form to load fully
    b.click(b.xp("clear_button"), "Clear filters")
    if b.exists(b.xp("date_checkbox"), timeout=2):
        b.set_checkbox(b.xp("date_checkbox"), False, "Untick the creation-date filter")
    b.paste(b.xp("act_input"), act, f"Act number = {act}")
    b.set_checkbox(b.xp("act_checkbox"), True, "Tick the act-number filter")
    b.click(b.xp("apply_button"), "Apply (search)")
    return b.exists(b.xp("result_row", act=act), timeout=b.page_timeout)


def accept_act(b, act: str) -> bool:
    """Row menu -> Accept for processing -> Apply -> Yes. False if the option is missing."""
    b.click(b.xp("row_menu", act=act), "Row menu")
    if not b.exists(b.xp("accept_option"), timeout=5):
        b.press_escape()
        return False
    b.click(b.xp("accept_option"), "Accept for processing")
    b.click(b.xp("apply_button"), "Apply (dialog)", last=True)
    b.click(b.xp("yes_button"), "Yes", last=True)
    return True


def confirm_gps(b, note: str) -> str:
    """GPS row -> Edit -> Note -> Apply -> Yes. Returns 'done', 'already' or 'unconfirmed'."""
    b.find(b.xp("gps_cell"), timeout=b.page_timeout)

    if b.exists(b.xp("gps_done"), timeout=1):
        return "already"

    b.click(b.xp("gps_cell"), "GPS row")
    b.click(b.xp("edit_option"), "Edit")
    b.type(b.xp("note_textarea"), note, "Fill the note field", last=True)
    b.click(b.xp("apply_button"), "Apply (edit)", last=True)
    b.click(b.xp("yes_button"), "Yes", last=True)

    if b.exists(b.xp("gps_done"), timeout=b.element_timeout):
        return "done"
    return "unconfirmed"


def close_act_dialog(b):
    try:
        b.click(b.xp("act_dialog_close"), "Close the act dialog", timeout=5, last=True)
    except TimeoutException:
        b.press_escape(2)


def process_act(b, act: str, note: str):
    """Full workflow for one act. Returns (status, message)."""
    b.ensure_logged_in()
    open_new_acts(b)

    if not search_act(b, act):
        return SKIP, "Not found among new inspection acts"

    if not accept_act(b, act):
        return SKIP, "'Accept for processing' option not available"

    gps = confirm_gps(b, note)
    close_act_dialog(b)

    if gps == "done":
        return OK, "GPS confirmed"
    if gps == "already":
        return OK, "GPS was already confirmed"
    return CHECK, "GPS status did not change to 'changes applied' - check manually"
