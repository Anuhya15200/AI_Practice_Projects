import jwt
from jwt import PyJWKClient
from jwt.exceptions import PyJWKClientError

KEYCLOAK_URL = "http://localhost:8080"
REALM_NAME = "mcp-employee"

ISSUER = f"{KEYCLOAK_URL}/realms/{REALM_NAME}"
JWKS_URL = f"{ISSUER}/protocol/openid-connect/certs"

EXPECTED_AUDIENCE = "mcp-api"

# Fetch and cache Keycloak public signing keys
jwks_client = PyJWKClient(
    JWKS_URL,
    cache_keys=True
)


def validate_access_token(access_token):

    try:
        # Step 1: Get the signing key from Keycloak
        signing_key = jwks_client.get_signing_key_from_jwt(
            access_token
        )

        # Step 2: Validate the JWT
        payload = jwt.decode(
            access_token,
            signing_key.key,
            algorithms=["RS256"],
            audience=EXPECTED_AUDIENCE,
            issuer=ISSUER,
            leeway=30,
            options={
                "require": [
                    "exp",
                    "iss",
                    "aud",
                    "sub",
                    "iat"
                ],
                "verify_nbf": True
            }
        )

        return payload

    except jwt.ExpiredSignatureError:
        raise ValueError("Access token has expired")

    except jwt.InvalidAudienceError:
        raise ValueError("Invalid token audience")

    except jwt.InvalidIssuerError:
        raise ValueError("Invalid token issuer")

    except jwt.ImmatureSignatureError:
        raise ValueError("Access token is not valid yet")

    except jwt.InvalidIssuedAtError:
        raise ValueError("Invalid token issued-at time")

    except PyJWKClientError:
        raise ValueError("Unable to retrieve Keycloak signing keys")

    except jwt.InvalidTokenError:
        raise ValueError("Invalid access token")


def get_user_roles(payload):

    realm_access = payload.get("realm_access", {})

    return realm_access.get("roles", [])


if __name__ == "__main__":

    print("JWT Validator is ready.")
    print("Issuer:", ISSUER)
    print("Expected Audience:", EXPECTED_AUDIENCE)
    print("Algorithm: RS256")
    print("Clock tolerance: 30 seconds")