from dataclasses import dataclass


@dataclass
class GoogleSelectors:
    BASE_URL = "https://console.cloud.google.com"

    EMAIL_INPUT = "input[type='email']"
    NEXT_BUTTON = "#identifierNext, button:has-text('Next')"
    PASSWORD_INPUT = "input[type='password']"
    PASSWORD_NEXT = "#passwordNext"

    PROJECT_SEARCH_INPUT = "input[placeholder='Search for project'], input[placeholder='Search projects']"
    PROJECT_ITEM = "cds-select-item, [role='option']"
    SELECT_PROJECT_BUTTON = "button:has-text('Select'), button:has-text('Open')"
    PROJECT_SELECTOR_BUTTON = "[aria-label='Select a project'], button:has-text('Select a project'), .cfc-project-selector"

    API_MENU = "[ng-if*='api']"
    CREDENTIALS_MENU = "[href*='credentials']"
    CREATE_CREDENTIALS_BUTTON = "button:has-text('Create Credentials'), button:has-text('Create credentials')"
    OAUTH_CLIENT_ID_OPTION = "button:has-text('OAuth client ID'), [role='menuitem']:has-text('OAuth client ID')"

    APP_TYPE_DROPDOWN = "[aria-label='Application type'], mat-select, cfc-select"
    APP_TYPE_WEB = "[value='WEB'], mat-option:has-text('Web application'), [role='option']:has-text('Web application')"
    APP_TYPE_DESKTOP = "[value='DESKTOP'], mat-option:has-text('Desktop app'), [role='option']:has-text('Desktop app')"
    APP_TYPE_ANDROID = "[value='ANDROID'], mat-option:has-text('Android'), [role='option']:has-text('Android')"
    APP_TYPE_IOS = "[value='IOS'], mat-option:has-text('iOS'), [role='option']:has-text('iOS')"
    APP_TYPE_TVS = "[value='TV_LIMITED_INPUT'], mat-option:has-text('TVs'), [role='option']:has-text('TVs')"
    APP_TYPE_UWP = "[value='UWP'], mat-option:has-text('Universal Windows'), [role='option']:has-text('Universal Windows')"
    
    NAME_INPUT = "input[aria-label='Name'], input[formcontrolname='name'], input[name='name']"
    
    ADD_URI_BUTTON = "button:has-text('Add URI'), button:has-text('+ Add URI')"
    ORIGIN_INPUT = "input[placeholder*='example.com'], input[aria-label*='JavaScript origin']"
    REDIRECT_URI_INPUT = "input[placeholder*='oauth2callback'], input[aria-label*='redirect URI']"
    
    CREATE_BUTTON = "button:has-text('Create'), button[type='submit']:has-text('Create')"
    SAVE_BUTTON = "button:has-text('Save'), button[type='submit']:has-text('Save')"

    CLIENT_ID_DISPLAY = "cds-copy-to-clipboard[data-id='client-id'], [data-testid='client-id'] code, .client-id code"
    CLIENT_SECRET_DISPLAY = "cds-copy-to-clipboard[data-id='client-secret'], [data-testid='client-secret'] code, .client-secret code"
    CLOSE_DIALOG_BUTTON = "button:has-text('OK'), button:has-text('Close'), button[aria-label='Close']"
    DOWNLOAD_JSON_BUTTON = "button:has-text('Download JSON'), a:has-text('Download JSON')"

    CONSENT_SCREEN_LINK = "a:has-text('OAuth consent screen'), a[href*='consent']"
    CONSENT_INTERNAL_RADIO = "input[value='INTERNAL'], mat-radio-button:has-text('Internal')"
    CONSENT_EXTERNAL_RADIO = "input[value='EXTERNAL'], mat-radio-button:has-text('External')"
    CONSENT_CREATE_BUTTON = "button:has-text('Create'), button[type='submit']"
    
    CONSENT_APP_NAME_INPUT = "input[formcontrolname='appName'], input[aria-label='App name'], input[name='appName']"
    CONSENT_USER_SUPPORT_EMAIL = "input[formcontrolname='supportEmail'], input[aria-label='User support email'], mat-select[formcontrolname='supportEmail']"
    CONSENT_APP_LOGO_UPLOAD = "input[type='file'][accept*='image'], button:has-text('Upload file')"
    CONSENT_HOMEPAGE_URL = "input[formcontrolname='homepageUri'], input[aria-label='Application home page']"
    CONSENT_PRIVACY_POLICY_URL = "input[formcontrolname='privacyPolicyUri'], input[aria-label='Application privacy policy link']"
    CONSENT_TERMS_OF_SERVICE_URL = "input[formcontrolname='tosUri'], input[aria-label='Application terms of service link']"
    CONSENT_AUTHORIZED_DOMAINS = "input[formcontrolname='authorizedDomain'], input[aria-label='Authorized domain']"
    CONSENT_ADD_DOMAIN_BUTTON = "button:has-text('Add Domain'), button:has-text('+ Add domain')"
    CONSENT_DEVELOPER_EMAIL = "input[formcontrolname='developerEmail'], input[aria-label='Developer contact information']"
    CONSENT_ADD_EMAIL_BUTTON = "button:has-text('Add email'), button:has-text('+ Add email')"
    
    SAVE_AND_CONTINUE_BUTTON = "button:has-text('Save and Continue'), button:has-text('Save and continue')"
    BACK_BUTTON = "button:has-text('Back')"
    
    SCOPES_ADD_BUTTON = "button:has-text('Add or Remove Scopes'), button:has-text('Add or remove scopes')"
    SCOPES_FILTER_INPUT = "input[placeholder*='Filter'], input[aria-label*='Filter scopes']"
    SCOPES_CHECKBOX = "mat-checkbox, input[type='checkbox']"
    SCOPES_UPDATE_BUTTON = "button:has-text('Update'), button:has-text('Save')"
    
    TEST_USERS_ADD_BUTTON = "button:has-text('Add Users'), button:has-text('+ Add users')"
    TEST_USERS_INPUT = "input[placeholder*='email'], textarea[placeholder*='email']"
    TEST_USERS_SAVE_BUTTON = "button:has-text('Add'), button:has-text('Save')"
    
    OAUTH_CLIENTS_TABLE = "table, cfc-table, mat-table"
    OAUTH_CLIENT_ROW = "tr, mat-row, [role='row']"
    OAUTH_CLIENT_NAME_CELL = "td:first-child, mat-cell:first-child"
    OAUTH_CLIENT_DELETE_BUTTON = "button:has-text('Delete'), button[aria-label='Delete']"
    OAUTH_CLIENT_EDIT_BUTTON = "button:has-text('Edit'), a:has-text('Edit')"
    
    DELETE_CONFIRM_INPUT = "input[type='text'], input[aria-label*='confirm']"
    DELETE_CONFIRM_BUTTON = "button:has-text('Delete'), button[type='submit']:has-text('Delete')"
