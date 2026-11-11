import secrets
import hashlib
import base64
import json
import webbrowser
import urllib.parse
import urllib.request

from http.server import HTTPServer, BaseHTTPRequestHandler


# ==================================================
# 1. KEYCLOAK CONFIGURATION
# ==================================================

KEYCLOAK_URL = "http://localhost:8080"

REALM_NAME = "mcp-employee"

CLIENT_ID = "mcp-gemini-client"

REDIRECT_URI = "http://127.0.0.1:8765/callback"

ISSUER = f"{KEYCLOAK_URL}/realms/{REALM_NAME}"

AUTHORIZATION_ENDPOINT = (
    f"{ISSUER}/protocol/openid-connect/auth"
)

TOKEN_ENDPOINT = (
    f"{ISSUER}/protocol/openid-connect/token"
)


# ==================================================
# 2. GENERATE PKCE CODE VERIFIER
# ==================================================

def generate_code_verifier():

    return secrets.token_urlsafe(64)


# ==================================================
# 3. GENERATE PKCE CODE CHALLENGE
# ==================================================

def generate_code_challenge(code_verifier):

    digest = hashlib.sha256(
        code_verifier.encode("ascii")
    ).digest()

    challenge = base64.urlsafe_b64encode(
        digest
    ).decode("ascii").rstrip("=")

    return challenge


# ==================================================
# 4. CALLBACK SERVER
# ==================================================

class OAuthCallbackHandler(BaseHTTPRequestHandler):

    authorization_code = None

    received_state = None

    error = None

    def do_GET(self):

        parsed_url = urllib.parse.urlparse(
            self.path
        )

        query_params = urllib.parse.parse_qs(
            parsed_url.query
        )

        OAuthCallbackHandler.authorization_code = (
            query_params.get("code", [None])[0]
        )

        OAuthCallbackHandler.received_state = (
            query_params.get("state", [None])[0]
        )

        OAuthCallbackHandler.error = (
            query_params.get("error", [None])[0]
        )

        self.send_response(200)

        self.send_header(
            "Content-Type",
            "text/html"
        )

        self.end_headers()

        if OAuthCallbackHandler.authorization_code:

            self.wfile.write(
                b"""
                <html>
                <body>
                    <h2>Authentication successful!</h2>
                    <p>You can close this browser window.</p>
                </body>
                </html>
                """
            )

        else:

            self.wfile.write(
                b"""
                <html>
                <body>
                    <h2>Authentication failed.</h2>
                    <p>Please check the Python terminal.</p>
                </body>
                </html>
                """
            )

    def log_message(self, format, *args):
        pass


# ==================================================
# 5. EXCHANGE AUTHORIZATION CODE FOR ACCESS TOKEN
# ==================================================

def exchange_code_for_token(
    authorization_code,
    code_verifier
):

    data = {
        "grant_type": "authorization_code",
        "client_id": CLIENT_ID,
        "code": authorization_code,
        "redirect_uri": REDIRECT_URI,
        "code_verifier": code_verifier
    }

    encoded_data = urllib.parse.urlencode(
        data
    ).encode("utf-8")

    request = urllib.request.Request(
        TOKEN_ENDPOINT,
        data=encoded_data,
        headers={
            "Content-Type": "application/x-www-form-urlencoded"
        },
        method="POST"
    )

    with urllib.request.urlopen(
        request,
        timeout=30
    ) as response:

        return json.loads(
            response.read().decode("utf-8")
        )


# ==================================================
# 6. DECODE JWT PAYLOAD FOR DISPLAY
# ==================================================

def decode_jwt_payload(access_token):

    parts = access_token.split(".")

    if len(parts) != 3:
        raise ValueError("Invalid JWT format")

    payload = parts[1]

    payload += "=" * (-len(payload) % 4)

    decoded = base64.urlsafe_b64decode(
        payload
    )

    return json.loads(
        decoded.decode("utf-8")
    )


# ==================================================
# 7. MAIN OAUTH LOGIN
# ==================================================

def login():

    print("=" * 60)

    print("KEYCLOAK OAUTH LOGIN")

    print("=" * 60)

    # Generate PKCE verifier.
    code_verifier = generate_code_verifier()

    # Generate PKCE challenge.
    code_challenge = generate_code_challenge(
        code_verifier
    )

    # Generate CSRF protection state.
    state = secrets.token_urlsafe(32)

    # --------------------------------------------------
    # BUILD AUTHORIZATION URL
    # --------------------------------------------------

    authorization_params = {

        "client_id": CLIENT_ID,

        "response_type": "code",

        "scope": "openid profile email",

        "redirect_uri": REDIRECT_URI,

        "state": state,

        "code_challenge": code_challenge,

        "code_challenge_method": "S256"
    }

    authorization_url = (
        AUTHORIZATION_ENDPOINT
        + "?"
        + urllib.parse.urlencode(
            authorization_params
        )
    )

    print("\nOpening Keycloak login page...")

    # --------------------------------------------------
    # START LOCAL CALLBACK SERVER
    # --------------------------------------------------

    OAuthCallbackHandler.authorization_code = None

    OAuthCallbackHandler.received_state = None

    OAuthCallbackHandler.error = None

    callback_server = HTTPServer(
        ("127.0.0.1", 8765),
        OAuthCallbackHandler
    )

    try:

        # Open browser.
        webbrowser.open(authorization_url)

        print("\nPlease log in through your browser.")

        print("Waiting for Keycloak callback...")

        callback_server.timeout = 180

        callback_server.handle_request()

    finally:

        callback_server.server_close()

    # --------------------------------------------------
    # VALIDATE CALLBACK
    # --------------------------------------------------

    authorization_code = (
        OAuthCallbackHandler.authorization_code
    )

    received_state = (
        OAuthCallbackHandler.received_state
    )

    if OAuthCallbackHandler.error:

        raise Exception(
            f"Keycloak authentication failed: "
            f"{OAuthCallbackHandler.error}"
        )

    if not authorization_code:

        raise Exception(
            "Authorization code was not received."
        )

    if received_state != state:

        raise Exception(
            "Invalid OAuth state. Possible CSRF attack."
        )

    print("\nAuthorization code received successfully!")

    # --------------------------------------------------
    # EXCHANGE CODE FOR TOKEN
    # --------------------------------------------------

    print("\nExchanging authorization code for tokens...")

    token_response = exchange_code_for_token(
        authorization_code,
        code_verifier
    )

    access_token = token_response["access_token"]

    print("\nAccess token received successfully!")

    # --------------------------------------------------
    # DISPLAY TOKEN INFORMATION
    # --------------------------------------------------

    payload = decode_jwt_payload(
        access_token
    )

    print("\nJWT PAYLOAD INFORMATION")

    print("-" * 50)

    print(
        "Username:",
        payload.get("preferred_username")
    )

    print(
        "Issuer:",
        payload.get("iss")
    )

    print(
        "Audience:",
        payload.get("aud")
    )

    print(
        "Realm roles:",
        payload.get("realm_access", {}).get("roles", [])
    )

    print(
        "Token expiry:",
        payload.get("exp")
    )

    print("-" * 50)

    print("\nOAuth login completed successfully!")

    # Return tokens for future MCP integration.
    return token_response


# ==================================================
# 8. APPLICATION ENTRY POINT
# ==================================================

if __name__ == "__main__":

    try:

        tokens = login()

        print("\nReceived token types:")

        print(
            list(tokens.keys())
        )

    except Exception as error:

        print("\nOAuth Error:", error)

def refresh_access_token(refresh_token):

    token_data = {
        "grant_type": "refresh_token",
        "client_id": CLIENT_ID,
        "refresh_token": refresh_token
    }

    encoded_data = urllib.parse.urlencode(token_data).encode()

    request = urllib.request.Request(
        TOKEN_ENDPOINT,
        data=encoded_data,
        headers={
            "Content-Type": "application/x-www-form-urlencoded"
        },
        method="POST"
    )

    try:
        with urllib.request.urlopen(request) as response:
            token_response = json.loads(response.read().decode())

        print("Access token refreshed successfully!")

        return token_response

    except urllib.error.HTTPError as error:
        error_details = error.read().decode()

        raise Exception(
            f"Token refresh failed: {error_details}"
        )