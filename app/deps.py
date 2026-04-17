import logging
from uuid import UUID

import jwt
from fastapi import Depends, HTTPException, Query, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.auth.clerk_jwt import verify_clerk_session_jwt
from app.auth.security import decode_token
from app.config import settings
from app.database import get_db
from app.models import OrganizationMembership, OrgMembershipRole, User
from app.services.clerk_users import get_or_create_user_from_clerk

logger = logging.getLogger(__name__)

bearer = HTTPBearer(auto_error=False)


def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
) -> User:
    if creds is None or creds.scheme.lower() != "bearer":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    token = creds.credentials
    try:
        header = jwt.get_unverified_header(token)
    except jwt.PyJWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    alg = header.get("alg")

    if alg == "HS256":
        user_id = decode_token(token)
        if user_id is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")
        user = db.get(User, user_id)
        if user is None or not user.is_active:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
        return user

    if alg == "RS256":
        if not settings.clerk_enabled or not settings.clerk_issuer.strip():
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=(
                    "Clerk is not configured on the API: set CLERK_ENABLED=true and CLERK_ISSUER "
                    "to your Clerk Frontend API URL (Clerk Dashboard → API keys → copy Frontend API URL / issuer), "
                    "then restart the API."
                ),
            )
        try:
            claims = verify_clerk_session_jwt(token)
        except jwt.InvalidTokenError as exc:
            logger.info("Clerk JWT invalid: %s", exc)
            # PyJWT uses "Signature has expired" — clearer for API clients than JWT jargon
            detail = (
                "Session expired; sign in again or refresh the page for a new Clerk session token."
                if isinstance(exc, jwt.ExpiredSignatureError)
                else str(exc)
            )
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=detail) from exc
        except jwt.PyJWTError as exc:
            logger.info("Clerk JWT verification failed: %s", exc)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=(
                    "Clerk session token could not be verified (signature/expiry/JWKS). "
                    "Ensure CLERK_ISSUER matches your Clerk Frontend API URL, the session is current, "
                    "and the API container can reach HTTPS to fetch Clerk JWKS."
                ),
            ) from exc
        user = get_or_create_user_from_clerk(db, claims)
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=(
                    "Clerk session could not be mapped to a user. "
                    "Add an email claim to the Clerk session token, or ensure a matching user exists."
                ),
            )
        return user

    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")


def require_platform_owner(user: User = Depends(get_current_user)) -> User:
    if not user.is_platform_owner:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Platform owner only")
    return user


def require_metrics_viewer(
    organization_id: UUID | None = Query(
        None,
        description="Scope metrics to one organization. Required unless the user is a platform owner.",
    ),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> tuple[User, UUID | None]:
    """Platform owners may pass optional org scope; org owners must pass their org id."""
    if user.is_platform_owner:
        return (user, organization_id)

    if organization_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="organization_id query parameter is required for metrics",
        )
    m = (
        db.query(OrganizationMembership)
        .filter(
            OrganizationMembership.user_id == user.id,
            OrganizationMembership.organization_id == organization_id,
        )
        .one_or_none()
    )
    if m is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not a member of this organization")
    if m.role != OrgMembershipRole.org_owner.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Organization owner role required to view metrics",
        )
    return (user, organization_id)


