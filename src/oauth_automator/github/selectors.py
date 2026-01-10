from dataclasses import dataclass


@dataclass
class GitHubSelectors:
    LOGIN_INPUT = "input[name='login']"
    LOGGED_IN_META = 'meta[name="user-login"]'

    PASSKEY_INDICATORS = [
        "text='Passkey'",
        "text='Use passkey'",
        "button:has-text('Use passkey')",
    ]
    PASSWORD_LINK_SELECTORS = [
        "a:has-text('Use your password')",
        "text='Use your password'",
        "a[href*='password']",
    ]
    SUDO_INDICATORS = [
        "text='Confirm password'",
        "text='Confirm user'",
        "input[name='password']",
        "input[type='password']",
    ]
    PASSWORD_INPUT = "input[name='password'], input[type='password']"
    SUBMIT_BUTTONS = [
        'button[type="submit"]',
        'button:has-text("Confirm")',
        'button:has-text("Verify")',
        'input[type="submit"]',
    ]

    APP_NAME_INPUT = 'input[name="oauth_application[name]"]'
    APP_URL_INPUT = 'input[name="oauth_application[url]"]'
    APP_DESC_INPUT = 'textarea[name="oauth_application[description]"]'
    CALLBACK_URL_INPUT = 'input[name="oauth_application[callback_url]"]'
    REGISTER_BUTTON = 'button:has-text("Register application")'
    CLIENT_ID_DISPLAY = ".listgroup-item code, code"

    GENERATE_SECRET_BUTTONS = [
        'button:has-text("Generate a new client secret")',
        'summary:has-text("Generate a new client secret")',
        "#js-oauth-reg-new-client-secret",
        'input[type="submit"][value*="client secret" i]',
        'a:has-text("Generate a new client secret")',
        'form[action*="secret"] button[type="submit"]',
        'button:has-text("Generate client secret")',
        '[data-confirm]:has-text("Generate")',
    ]

    APP_LINKS = [
        'a[href*="/settings/applications/"][href*="/"]',
        '.listgroup a[href*="/settings/applications/"]',
        'li a[href*="/settings/applications/"]',
    ]
    NEXT_PAGE_LINK = 'a.next_page, a[rel="next"]'

    DELETE_BUTTONS = [
        'button:has-text("Delete")',
        'summary:has-text("Delete")',
        'button[type="submit"]:has-text("Delete")',
        'a:has-text("Delete application")',
    ]
    CONFIRM_DELETE_INPUT = 'input[name="verify"], input[aria-label*="confirm"]'
    CONFIRM_DELETE_BUTTONS = [
        'button:has-text(" Delete this OAuth application")',
        'button:has-text("Delete this OAuth application")',
        'button[type="submit"]:has-text("Delete")',
        'button.btn-danger[type="submit"]',
    ]
