
import requests

def inspect_aidailybrief(edition_url):
    urls = {
        "digest": f"{edition_url}.md",
        "transcript": f"{edition_url}/transcript.md",
    }

    for name, url in urls.items():
        response = requests.get(
            url,
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=20
        )
        response.raise_for_status()

        content = response.text

        print(f"\n{name.upper()}")
        print(f"Characters: {len(content):,}")
        print(f"Words: {len(content.split()):,}")
        print(f"Preview:\n{content[:1200]}")

        with open(
            f"aidailybrief_{name}.md",
            "w",
            encoding="utf-8"
        ) as f:
            f.write(content)


if __name__ == "__main__":
    
    inspect_aidailybrief( "https://aidailybrief.ai/e/2026-10-30")
