"""
State router — determines agent state from GET /accounts/me response.
Routes per skill.md State Router logic.
"""
from bot.utils.logger import get_logger

log = get_logger(__name__)

# States
NO_ACCOUNT = "NO_ACCOUNT"
NO_IDENTITY = "NO_IDENTITY"
IN_GAME = "IN_GAME"
READY_PAID = "READY_PAID"
READY_FREE = "READY_FREE"
ERROR = "ERROR"


def determine_state(me_response: dict, identity_response: dict | None = None) -> tuple[str, dict]:
    """
    Analyze /accounts/me response → return (state, context).
    Context contains relevant data for the next step.

    identity_response: optional result of GET /identity (same source as
    setup.identity.ensure_identity).  Used as a fallback when
    readiness.erc8004Id is absent from /accounts/me — fixes the mismatch
    where the identity registry is already populated but /accounts/me has
    not yet reflected it.
    """
    readiness = me_response.get("readiness", {})
    current_games = me_response.get("currentGames", [])

    # Check for active game
    for game in current_games:
        if game.get("gameStatus") in ("waiting", "running"):
            log.info("Active game found: %s (status=%s)",
                     game["gameId"], game["gameStatus"])
            return IN_GAME, {
                "game_id": game["gameId"],
                "agent_id": game["agentId"],
                "game_status": game["gameStatus"],
                "entry_type": game.get("entryType", "free"),
                "is_alive": game.get("isAlive", True),
            }

    # Check ERC-8004 identity — prefer /accounts/me readiness field, but
    # fall back to the dedicated GET /identity response when the field is
    # absent.  This prevents a state mismatch where setup.identity already
    # confirmed registration but /accounts/me still returns erc8004Id=null.
    erc8004_id = readiness.get("erc8004Id")
    if erc8004_id is None and identity_response is not None:
        erc8004_id = identity_response.get("erc8004Id")
        if erc8004_id is not None:
            log.info(
                "erc8004Id absent in /accounts/me readiness; "
                "using GET /identity fallback: tokenId=%s", erc8004_id
            )
    if erc8004_id is None:
        log.info("No ERC-8004 identity registered")
        return NO_IDENTITY, {}

    # Check paid readiness
    if readiness.get("paidReady", False):
        balance = me_response.get("balance", 0)
        if balance >= 500:  # PAID_ENTRY_FEE_SMOLTZ from economy.md
            log.info("Paid ready: balance=%d sMoltz", balance)
            return READY_PAID, {"balance": balance}

    # Default to free
    log.info("Ready for free play")
    return READY_FREE, {
        "balance": me_response.get("balance", 0),
        "wallet_address": readiness.get("walletAddress"),
        "whitelist_approved": readiness.get("whitelistApproved", False),
    }
