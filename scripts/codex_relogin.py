"""Sign in to the official Codex runtime using a ChatGPT subscription."""
import webbrowser

from openai_codex import Codex


def main() -> int:
    with Codex() as codex:
        login = codex.login_chatgpt()
        print("Open this URL to sign in:", login.auth_url, flush=True)
        webbrowser.open(login.auth_url)
        completed = login.wait()
        if not completed.success:
            print("Login failed:", completed.error)
            return 1
        print("ChatGPT sign-in complete.")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
