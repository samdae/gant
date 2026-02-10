import base64
import hashlib
import json
import logging
import os
import secrets
import sys
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any, Dict, Iterator, List, Optional, Union, Callable
from urllib.parse import parse_qs, urlencode, urlparse
import urllib.request
import urllib.error

from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.tools import BaseTool
from langchain_core.runnables import Runnable

from .base_client import BaseLLMClient

# --- Constants ---
CLIENT_ID = base64.b64decode(
    "MTA3MTAwNjA2MDU5MS10bWhzc2luMmgyMWxjcmUyMzV2dG9sb2poNGc0MDNlcC5hcHBzLmdvb2dsZXVzZXJjb250ZW50LmNvbQ=="
).decode("utf-8")
CLIENT_SECRET = base64.b64decode("R09DU1BYLUs1OEZXUjQ4NkxkTEoxbUxCOHNYQzR6NnFEQWY=").decode("utf-8")
REDIRECT_PORT = 51121
REDIRECT_URI = f"http://localhost:{REDIRECT_PORT}/oauth-callback"
AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"

# Use cloudcode-pa for everything since fetching models works there
BASE_URL = "https://cloudcode-pa.googleapis.com"
LOAD_CODE_ASSIST_PATH = "/v1internal:loadCodeAssist"

# We know this endpoint exists (returned 400), so focus probing here
TARGET_ENDPOINT = "/v1internal:generateContent"

COMMON_HEADERS = {
    "User-Agent": "antigravity",
    "X-Goog-Api-Client": "google-cloud-sdk vscode_cloudshelleditor/0.1",
    "Content-Type": "application/json",
}

SCOPES = [
    "https://www.googleapis.com/auth/cloud-platform",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
    "https://www.googleapis.com/auth/cclog",
    "https://www.googleapis.com/auth/experimentsandconfigs",
]

logger = logging.getLogger(__name__)

# --- OAuth & Token Management ---
TOKEN_FILE = os.path.expanduser("~/.antigravity_tokens.json")

class AntigravityAuth:
    _instance = None
    access_token: Optional[str] = None
    refresh_token: Optional[str] = None
    expires_at: float = 0
    project_id: Optional[str] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(AntigravityAuth, cls).__new__(cls)
            cls._instance._load_tokens()
        return cls._instance

    def _save_tokens(self):
        """Save refresh_token and project_id to disk."""
        data = {}
        if self.refresh_token:
            data["refresh_token"] = self.refresh_token
        if self.project_id:
            data["project_id"] = self.project_id
        try:
            with open(TOKEN_FILE, "w") as f:
                json.dump(data, f, indent=2)
            print(f"[Antigravity] Tokens saved to {TOKEN_FILE}")
        except Exception as e:
            logger.warning(f"[Antigravity] Failed to save tokens: {e}")

    def _load_tokens(self):
        """Load saved tokens from disk."""
        if not os.path.exists(TOKEN_FILE):
            return
        try:
            with open(TOKEN_FILE, "r") as f:
                data = json.load(f)
            self.refresh_token = data.get("refresh_token")
            self.project_id = data.get("project_id")
            if self.refresh_token:
                print(f"[Antigravity] Loaded saved tokens from {TOKEN_FILE}")
        except Exception as e:
            logger.warning(f"[Antigravity] Failed to load tokens: {e}")

    def _refresh_access_token(self) -> bool:
        """Use refresh_token to get a new access_token without browser."""
        if not self.refresh_token:
            return False
        try:
            data = {
                "client_id": CLIENT_ID,
                "client_secret": CLIENT_SECRET,
                "refresh_token": self.refresh_token,
                "grant_type": "refresh_token",
            }
            data_encoded = urlencode(data).encode("utf-8")
            req = urllib.request.Request(TOKEN_URL, data=data_encoded, method="POST")
            with urllib.request.urlopen(req) as response:
                tokens = json.loads(response.read().decode("utf-8"))
            self.access_token = tokens["access_token"]
            self.expires_at = time.time() + tokens.get("expires_in", 3600) - 300
            # Google may issue a new refresh_token
            if tokens.get("refresh_token"):
                self.refresh_token = tokens["refresh_token"]
                self._save_tokens()
            print("[Antigravity] Token refreshed (no browser needed)")
            return True
        except Exception as e:
            logger.warning(f"[Antigravity] Refresh failed, will try browser auth: {e}")
            self.refresh_token = None
            return False

    def _generate_pkce(self):
        verifier = secrets.token_urlsafe(32)
        digest = hashlib.sha256(verifier.encode("utf-8")).digest()
        challenge = base64.urlsafe_b64encode(digest).decode("utf-8").replace("=", "")
        return verifier, challenge

    def _get_auth_code(self, verifier, challenge):
        state = secrets.token_hex(16)
        params = {
            "client_id": CLIENT_ID,
            "response_type": "code",
            "redirect_uri": REDIRECT_URI,
            "scope": " ".join(SCOPES),
            "code_challenge": challenge,
            "code_challenge_method": "S256",
            "state": state,
            "access_type": "offline",
            "prompt": "consent",
        }
        url = f"{AUTH_URL}?{urlencode(params)}"

        class OAuthHandler(BaseHTTPRequestHandler):
            def do_GET(self):
                parsed = urlparse(self.path)
                if parsed.path != "/oauth-callback":
                    self.send_error(404)
                    return
                query = parse_qs(parsed.query)
                self.server.auth_code = query.get("code", [None])[0]
                self.server.auth_state = query.get("state", [None])[0]
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(b"<html><body><h1>Auth Complete</h1><p>Close this window.</p></body></html>")
            
            def log_message(self, format, *args):
                pass

        server = HTTPServer(("localhost", REDIRECT_PORT), OAuthHandler)
        server.auth_code = None
        
        print(f"\n[Antigravity] Please authenticate via browser: {url}\n")
        
        if not os.path.exists("/.dockerenv"):
            try:
                webbrowser.open(url)
            except:
                pass
        
        try:
            server.handle_request()
        except KeyboardInterrupt:
            return None
            
        if server.auth_state != state:
            raise Exception("State mismatch")
        
        return server.auth_code

    def _exchange_token(self, code, verifier):
        data = {
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": REDIRECT_URI,
            "code_verifier": verifier,
        }
        data_encoded = urlencode(data).encode("utf-8")
        req = urllib.request.Request(TOKEN_URL, data=data_encoded, method="POST")
        with urllib.request.urlopen(req) as response:
            return json.loads(response.read().decode("utf-8"))

    def _fetch_project_id(self):
        headers = COMMON_HEADERS.copy()
        headers["Authorization"] = f"Bearer {self.access_token}"
        body = {
            "metadata": {
                "ideType": "IDE_UNSPECIFIED",
                "platform": "PLATFORM_UNSPECIFIED",
                "pluginType": "GEMINI",
            }
        }
        req = urllib.request.Request(
            f"{BASE_URL}{LOAD_CODE_ASSIST_PATH}",
            data=json.dumps(body).encode("utf-8"),
            headers=headers,
            method="POST"
        )
        try:
            with urllib.request.urlopen(req) as response:
                data = json.loads(response.read().decode("utf-8"))
                proj = data.get("cloudaicompanionProject")
                if isinstance(proj, str): return proj
                if isinstance(proj, dict): return proj.get("id")
        except:
            pass
        return "rising-fact-p41fc"

    def ensure_token(self):
        # 1) Already have a valid token
        if self.access_token and time.time() < self.expires_at:
            return
        
        # 2) Try refresh_token (no browser needed)
        if self.refresh_token and self._refresh_access_token():
            if not self.project_id:
                self.project_id = self._fetch_project_id()
                self._save_tokens()
            return
        
        # 3) Full browser OAuth flow (first time or refresh failed)
        print("[Antigravity] Browser authentication required (first time or token expired)")
        verifier, challenge = self._generate_pkce()
        code = self._get_auth_code(verifier, challenge)
        if not code:
            raise Exception("Failed to get auth code")
            
        tokens = self._exchange_token(code, verifier)
        self.access_token = tokens["access_token"]
        self.refresh_token = tokens.get("refresh_token")
        self.expires_at = time.time() + tokens.get("expires_in", 3600) - 300
        
        if not self.project_id:
            self.project_id = self._fetch_project_id()
        
        # Save tokens for next run
        self._save_tokens()


# --- Gemini CLI OAuth (alternative auth) ---
GEMINI_CLI_CLIENT_ID = "681255809395-oo8ft2oprdrnp9e3aqf6av3hmdib135j.apps.googleusercontent.com"
GEMINI_CLI_CLIENT_SECRET = "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"
GEMINI_CLI_TOKEN_FILE = os.path.expanduser("~/.gemini/oauth_creds.json")
GEMINI_CLI_SCOPES = [
    "https://www.googleapis.com/auth/cloud-platform",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
]

class GeminiCLIAuth:
    """Auth using Gemini CLI's cached OAuth tokens (~/.gemini/oauth_creds.json).
    
    If gemini-cli has been authenticated, this will reuse those tokens.
    If not, it will do its own browser OAuth with gemini-cli's credentials.
    """
    _instance = None
    access_token: Optional[str] = None
    refresh_token: Optional[str] = None
    expires_at: float = 0
    project_id: Optional[str] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(GeminiCLIAuth, cls).__new__(cls)
            cls._instance._load_gemini_cli_tokens()
        return cls._instance

    def _load_gemini_cli_tokens(self):
        """Load tokens from gemini-cli's cached file."""
        if not os.path.exists(GEMINI_CLI_TOKEN_FILE):
            print(f"[GeminiCLI Auth] No cached tokens at {GEMINI_CLI_TOKEN_FILE}")
            print(f"[GeminiCLI Auth] Run 'gemini' once to authenticate first, or we'll do browser auth.")
            return
        try:
            with open(GEMINI_CLI_TOKEN_FILE, "r") as f:
                data = json.load(f)
            self.refresh_token = data.get("refresh_token")
            self.access_token = data.get("access_token")
            if self.access_token and data.get("expiry_date"):
                # gemini-cli stores expiry_date as epoch millis
                self.expires_at = data["expiry_date"] / 1000
            if self.refresh_token:
                print(f"[GeminiCLI Auth] Loaded gemini-cli tokens from {GEMINI_CLI_TOKEN_FILE}")
        except Exception as e:
            logger.warning(f"[GeminiCLI Auth] Failed to load tokens: {e}")

    def _refresh_access_token(self) -> bool:
        """Use refresh_token with gemini-cli's client credentials."""
        if not self.refresh_token:
            return False
        try:
            data = {
                "client_id": GEMINI_CLI_CLIENT_ID,
                "client_secret": GEMINI_CLI_CLIENT_SECRET,
                "refresh_token": self.refresh_token,
                "grant_type": "refresh_token",
            }
            data_encoded = urlencode(data).encode("utf-8")
            req = urllib.request.Request(TOKEN_URL, data=data_encoded, method="POST")
            with urllib.request.urlopen(req) as response:
                tokens = json.loads(response.read().decode("utf-8"))
            self.access_token = tokens["access_token"]
            self.expires_at = time.time() + tokens.get("expires_in", 3600) - 300
            if tokens.get("refresh_token"):
                self.refresh_token = tokens["refresh_token"]
            print("[GeminiCLI Auth] Token refreshed successfully")
            return True
        except Exception as e:
            logger.warning(f"[GeminiCLI Auth] Refresh failed: {e}")
            return False

    def _browser_auth(self):
        """Full browser OAuth flow using gemini-cli credentials."""
        state = secrets.token_hex(16)
        verifier = secrets.token_urlsafe(32)
        digest = hashlib.sha256(verifier.encode("utf-8")).digest()
        challenge = base64.urlsafe_b64encode(digest).decode("utf-8").replace("=", "")
        
        params = {
            "client_id": GEMINI_CLI_CLIENT_ID,
            "response_type": "code",
            "redirect_uri": REDIRECT_URI,
            "scope": " ".join(GEMINI_CLI_SCOPES),
            "code_challenge": challenge,
            "code_challenge_method": "S256",
            "state": state,
            "access_type": "offline",
            "prompt": "consent",
        }
        url = f"{AUTH_URL}?{urlencode(params)}"
        
        class OAuthHandler(BaseHTTPRequestHandler):
            def do_GET(self):
                parsed = urlparse(self.path)
                if parsed.path != "/oauth-callback":
                    self.send_error(404)
                    return
                query = parse_qs(parsed.query)
                self.server.auth_code = query.get("code", [None])[0]
                self.server.auth_state = query.get("state", [None])[0]
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(b"<html><body><h1>Auth Complete</h1><p>Close this window.</p></body></html>")
            
            def log_message(self, format, *args):
                pass
        
        server = HTTPServer(("localhost", REDIRECT_PORT), OAuthHandler)
        server.auth_code = None
        
        print(f"\n[GeminiCLI Auth] Please authenticate via browser: {url}\n")
        if not os.path.exists("/.dockerenv"):
            try:
                webbrowser.open(url)
            except:
                pass
        
        try:
            server.handle_request()
        except KeyboardInterrupt:
            raise Exception("Auth cancelled by user")
        
        if server.auth_state != state:
            raise Exception("State mismatch")
        
        code = server.auth_code
        if not code:
            raise Exception("Failed to get auth code")
        
        # Exchange code for tokens
        data = {
            "client_id": GEMINI_CLI_CLIENT_ID,
            "client_secret": GEMINI_CLI_CLIENT_SECRET,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": REDIRECT_URI,
            "code_verifier": verifier,
        }
        data_encoded = urlencode(data).encode("utf-8")
        req = urllib.request.Request(TOKEN_URL, data=data_encoded, method="POST")
        with urllib.request.urlopen(req) as response:
            tokens = json.loads(response.read().decode("utf-8"))
        
        self.access_token = tokens["access_token"]
        self.refresh_token = tokens.get("refresh_token")
        self.expires_at = time.time() + tokens.get("expires_in", 3600) - 300
        
        # Save back to gemini-cli's token file so both tools share tokens
        try:
            save_data = {
                "access_token": self.access_token,
                "refresh_token": self.refresh_token,
                "expiry_date": int(self.expires_at * 1000),
                "token_type": "Bearer",
            }
            os.makedirs(os.path.dirname(GEMINI_CLI_TOKEN_FILE), exist_ok=True)
            with open(GEMINI_CLI_TOKEN_FILE, "w") as f:
                json.dump(save_data, f, indent=2)
            print(f"[GeminiCLI Auth] Tokens saved to {GEMINI_CLI_TOKEN_FILE}")
        except Exception as e:
            logger.warning(f"[GeminiCLI Auth] Failed to save tokens: {e}")

    def _fetch_project_id(self):
        """Fetch project_id using gemini-cli-compatible headers."""
        import platform
        headers = {
            "User-Agent": f"GeminiCLI/1.0.0 ({platform.system()}; {platform.machine()})",
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.access_token}",
        }
        body = {
            "metadata": {
                "ideType": "IDE_UNSPECIFIED",
                "platform": "PLATFORM_UNSPECIFIED",
                "pluginType": "GEMINI",
            }
        }
        req = urllib.request.Request(
            f"{BASE_URL}{LOAD_CODE_ASSIST_PATH}",
            data=json.dumps(body).encode("utf-8"),
            headers=headers,
            method="POST"
        )
        try:
            with urllib.request.urlopen(req) as response:
                data = json.loads(response.read().decode("utf-8"))
                proj = data.get("cloudaicompanionProject")
                if isinstance(proj, str):
                    return proj
                if isinstance(proj, dict):
                    return proj.get("id")
        except Exception as e:
            print(f"[GeminiCLI Auth] WARNING: loadCodeAssist failed: {e}")
        return "rising-fact-p41fc"

    def ensure_token(self):
        """Same interface as AntigravityAuth.ensure_token()."""
        # 1) Already have a valid token
        if self.access_token and time.time() < self.expires_at:
            pass  # Token is valid, continue to project_id check below
        # 2) Try refresh
        elif self.refresh_token and self._refresh_access_token():
            pass  # Refreshed, continue to project_id check below
        else:
            # 3) Full browser auth
            print("[GeminiCLI Auth] Browser authentication required")
            self._browser_auth()
        
        # Always ensure project_id is set
        if not self.project_id:
            self.project_id = self._fetch_project_id()
            print(f"[GeminiCLI Auth] Project: {self.project_id}")


def get_auth(auth_mode: str = "antigravity"):
    """Factory function to get the appropriate auth instance."""
    if auth_mode == "gemini-cli":
        return GeminiCLIAuth()
    return AntigravityAuth()


# --- LangChain Custom Model ---
class ChatAntigravity(BaseChatModel):
    model: str = "gemini-3-pro-high"  # Default
    auth: Any = None  # Will be set by __init__ based on auth_mode
    auth_mode: str = "antigravity"  # "antigravity" or "gemini-cli"
    gemini_tools: Optional[List[Dict[str, Any]]] = None  # Gemini functionDeclarations
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if self.auth is None:
            self.auth = get_auth(self.auth_mode)
    
    @property
    def _llm_type(self) -> str:
        return "antigravity"

    @staticmethod
    def _langchain_tool_to_gemini(tool) -> Dict[str, Any]:
        """Convert a LangChain tool to Gemini functionDeclaration format."""
        if isinstance(tool, dict):
            # Already a dict schema
            schema = tool
        elif hasattr(tool, 'args_schema') and tool.args_schema:
            # LangChain BaseTool with Pydantic schema
            json_schema = tool.args_schema.schema()
            properties = {}
            for prop_name, prop_info in json_schema.get("properties", {}).items():
                prop_type = prop_info.get("type", "string")
                gemini_type = {
                    "string": "STRING", "integer": "INTEGER", "number": "NUMBER",
                    "boolean": "BOOLEAN", "array": "ARRAY", "object": "OBJECT",
                }.get(prop_type, "STRING")
                prop_def = {"type": gemini_type}
                if prop_info.get("description"):
                    prop_def["description"] = prop_info["description"]
                # Handle Annotated descriptions (LangChain puts these in 'title' sometimes)
                if not prop_def.get("description") and prop_info.get("title"):
                    prop_def["description"] = prop_info["title"]
                properties[prop_name] = prop_def
            
            schema = {
                "name": tool.name,
                "description": tool.description or f"Tool: {tool.name}",
                "parameters": {
                    "type": "OBJECT",
                    "properties": properties,
                    "required": json_schema.get("required", list(properties.keys())),
                }
            }
        else:
            # Minimal fallback
            schema = {
                "name": getattr(tool, 'name', str(tool)),
                "description": getattr(tool, 'description', ''),
            }
        return schema

    def bind_tools(
        self,
        tools: List[Union[Dict[str, Any], BaseTool, Callable, Any]],
        **kwargs: Any,
    ) -> "ChatAntigravity":
        """Convert LangChain tools to Gemini format and return new instance with tools."""
        gemini_decls = [self._langchain_tool_to_gemini(t) for t in tools]
        
        # Return a new ChatAntigravity with tools attached
        new_instance = ChatAntigravity(model=self.model, auth_mode=self.auth_mode)
        new_instance.auth = self.auth
        new_instance.gemini_tools = [{"functionDeclarations": gemini_decls}]
        
        tool_names = [d.get("name", "?") for d in gemini_decls]
        print(f"[Antigravity] Tools bound: {tool_names}")
        return new_instance

    def _generate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> ChatResult:
        self.auth.ensure_token()
        
        # Import ToolMessage here to avoid circular imports
        from langchain_core.messages import ToolMessage
        
        # Convert messages to Gemini format
        system_parts = []
        gemini_contents = []
        # Collect consecutive ToolMessages into a single user turn
        pending_tool_responses = []
        
        def flush_tool_responses():
            """Merge pending tool responses into a single user turn."""
            nonlocal pending_tool_responses
            if pending_tool_responses:
                gemini_contents.append({
                    "role": "user",
                    "parts": pending_tool_responses
                })
                pending_tool_responses = []
        
        for m in messages:
            if isinstance(m, ToolMessage):
                # Accumulate tool responses (don't flush yet — more may follow)
                pending_tool_responses.append({
                    "functionResponse": {
                        "name": m.name or "unknown_tool",
                        "response": {"result": m.content}
                    }
                })
            else:
                # Any non-ToolMessage flushes pending tool responses first
                flush_tool_responses()
                
                if isinstance(m, SystemMessage):
                    system_parts.append({"text": m.content})
                elif isinstance(m, AIMessage):
                    parts = []
                    # If AIMessage had tool_calls, convert back to functionCall parts
                    if hasattr(m, 'tool_calls') and m.tool_calls:
                        # Retrieve stored thoughtSignatures
                        saved_signatures = (m.additional_kwargs or {}).get("thought_signatures", {})
                        for tc in m.tool_calls:
                            part = {
                                "functionCall": {
                                    "name": tc["name"],
                                    "args": tc["args"]
                                }
                            }
                            # Re-attach thoughtSignature if we saved one for this tool call
                            sig = saved_signatures.get(tc["id"] or tc["name"])
                            if sig:
                                part["thoughtSignature"] = sig
                            parts.append(part)
                    else:
                        parts.append({"text": m.content or ""})
                    gemini_contents.append({"role": "model", "parts": parts})
                else:
                    # HumanMessage or other
                    gemini_contents.append({
                        "role": "user",
                        "parts": [{"text": m.content}]
                    })
        
        # Flush any remaining tool responses at end of messages
        flush_tool_responses()
            
        clean_model = self.model.replace("google-antigravity/", "").replace("google/", "")
        
        # Gemini-cli uses different model names than antigravity
        if self.auth_mode == "gemini-cli":
            GEMINI_CLI_MODEL_MAP = {
                "gemini-3-flash": "gemini-2.5-flash",
                "gemini-3-pro": "gemini-2.5-pro",
                "gemini-3-pro-high": "gemini-2.5-pro",
                "gemini-3-flash-lite": "gemini-2.5-flash-lite",
            }
            mapped_model = GEMINI_CLI_MODEL_MAP.get(clean_model, clean_model)
            if mapped_model != clean_model:
                print(f"[GeminiCLI Auth] Model mapped: {clean_model} -> {mapped_model}")
            clean_model = mapped_model
        
        # Prepare headers — gemini-cli uses different headers than antigravity
        if self.auth_mode == "gemini-cli":
            import platform
            headers = {
                "User-Agent": f"GeminiCLI/1.0.0/{clean_model} ({platform.system()}; {platform.machine()})",
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.auth.access_token}",
            }
        else:
            headers = COMMON_HEADERS.copy()
            headers["Authorization"] = f"Bearer {self.auth.access_token}"
        
        # Build request body
        request_body = {
            "contents": gemini_contents,
            "generationConfig": {
                "temperature": 0.7,
            }
        }
        
        # Add system instruction if present
        if system_parts:
            request_body["systemInstruction"] = {"parts": system_parts}
        
        # Add tools if bound
        if self.gemini_tools:
            request_body["tools"] = self.gemini_tools
        
        payload = {
            "model": clean_model,
            "project": self.auth.project_id or "default-project",
            "request": request_body,
        }
        
        # Model fallback chain for capacity exhaustion (503 only)
        # NOTE: flash-lite removed — too low quality for complex analysis tasks
        MODEL_FALLBACKS = {
            "gemini-2.5-pro": "gemini-2.5-flash",
            "gemini-3-pro-high": "gemini-3-pro-low",
            "gemini-3-pro-low": "gemini-3-flash",
        }
        MAX_RETRIES = 5
        
        url = f"{BASE_URL}{TARGET_ENDPOINT}"
        current_model = clean_model
        
        for attempt in range(MAX_RETRIES):
            payload["model"] = current_model
            
            try:
                logger.info(f"[Antigravity] Calling {url} with model={current_model} (attempt {attempt+1})")
                print(f"[Antigravity] Calling cloudcode-pa generateContent (model={current_model})...")
                
                req = urllib.request.Request(
                    url,
                    data=json.dumps(payload).encode("utf-8"),
                    headers=headers,
                    method="POST"
                )
                
                with urllib.request.urlopen(req) as response:
                    resp_data = json.loads(response.read().decode("utf-8"))
                    logger.info(f"[Antigravity] SUCCESS!")
                    print(f"[Antigravity] SUCCESS!")
                    
                    # Parse response
                    try:
                        inner = resp_data.get("response", resp_data)
                        candidate = inner["candidates"][0]
                        content = candidate.get("content", {})
                        parts = content.get("parts", [])
                        
                        # Check for functionCall parts (tool calling)
                        tool_calls = []
                        thought_signatures = {}  # id -> signature
                        text_parts = []
                        for part in parts:
                            if "functionCall" in part:
                                fc = part["functionCall"]
                                call_id = f"call_{fc['name']}_{secrets.token_hex(4)}"
                                tool_calls.append({
                                    "name": fc["name"],
                                    "args": fc.get("args", {}),
                                    "id": call_id,
                                })
                                # Capture thoughtSignature if present
                                if part.get("thoughtSignature"):
                                    thought_signatures[call_id] = part["thoughtSignature"]
                            elif "text" in part:
                                text_parts.append(part["text"])
                        
                        if tool_calls:
                            # Model wants to call tools
                            text = "\n".join(text_parts) if text_parts else ""
                            print(f"[Antigravity] Tool calls: {[tc['name'] for tc in tool_calls]}")
                            additional_kwargs = {}
                            if thought_signatures:
                                additional_kwargs["thought_signatures"] = thought_signatures
                            msg = AIMessage(content=text, tool_calls=tool_calls, additional_kwargs=additional_kwargs)
                            return ChatResult(generations=[ChatGeneration(message=msg)])
                        elif text_parts:
                            text = "\n".join(text_parts)
                        elif candidate.get("finishMessage"):
                            text = candidate["finishMessage"]
                        else:
                            text = json.dumps(resp_data)
                    except (KeyError, IndexError, TypeError):
                        logger.warning(f"[Antigravity] Non-standard response: {json.dumps(resp_data)[:300]}")
                        text = json.dumps(resp_data)
                    
                    return ChatResult(generations=[ChatGeneration(message=AIMessage(content=text))])
                    
            except urllib.error.HTTPError as e:
                err_body = e.read().decode('utf-8')
                
                # Handle 429 (rate limit) — retry same model after waiting
                if e.code == 429:
                    if attempt < MAX_RETRIES - 1:
                        wait_time = 30
                        print(f"[Antigravity] Rate limited (429), waiting {wait_time}s before retry... (attempt {attempt+1}/{MAX_RETRIES})")
                        time.sleep(wait_time)
                        continue
                
                # Handle 503 (capacity exhausted) — try fallback model
                if e.code == 503:
                    fallback = MODEL_FALLBACKS.get(current_model)
                    if fallback:
                        print(f"[Antigravity] {current_model} capacity exhausted (503), falling back to {fallback}...")
                        current_model = fallback
                        continue
                    elif attempt < MAX_RETRIES - 1:
                        wait_time = 2 ** (attempt + 1)
                        print(f"[Antigravity] Capacity exhausted, retrying in {wait_time}s... (attempt {attempt+1}/{MAX_RETRIES})")
                        time.sleep(wait_time)
                        continue
                
                logger.error(f"[Antigravity] Failed: {e.code} - {err_body[:500]}")
                print(f"[Antigravity] Failed: {e.code} - {err_body}")
                raise Exception(f"Antigravity API failed: {e.code} - {err_body}")
            except Exception as e:
                logger.error(f"[Antigravity] Error: {e}")
                print(f"[Antigravity] Error: {e}")
                raise
        
        raise Exception(f"Antigravity API failed after {MAX_RETRIES} retries")


class AntigravityClient(BaseLLMClient):
    """Client for Google Antigravity (Spoofed) models."""
    
    def get_llm(self) -> Any:
        return ChatAntigravity(model=self.model, **self.kwargs)

    def validate_model(self) -> bool:
        return True 
