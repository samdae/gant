"""Check both ends of the v4 report and position switches in installed Chrome.

Run against a running viewer: uv run --no-project --with playwright scripts/check-v4-segment-layout.py http://127.0.0.1:5173/v4/
"""

import argparse
from math import isclose

from playwright.sync_api import expect, sync_playwright


MEASURE = """button => {
    const rail = button.parentElement;
    const outer = rail.getBoundingClientRect(), box = button.getBoundingClientRect();
    const css = getComputedStyle(button), frame = getComputedStyle(rail);
    const first = button === rail.firstElementChild;
    const edge = first ? 'Left' : 'Right';
    // CSS reduces a large uniform border-radius to half the shortest dimension.
    const radius = (style, rect, corner) => Math.min(
        parseFloat(style['border' + corner + edge + 'Radius']), rect.height / 2, rect.width / 2);
    const inset = side => css.backgroundClip === 'padding-box' ? parseFloat(css['border' + side + 'Width']) : 0;
    return {
        top: box.top - outer.top + inset('Top'),
        bottom: outer.bottom - box.bottom + inset('Bottom'),
        side: (first ? box.left - outer.left : outer.right - box.right) + inset(edge),
        curves: ['Top', 'Bottom'].map(corner => [
            radius(frame, outer, corner), radius(css, box, corner) - inset(edge)]),
        height: outer.height,
        painted: css.backgroundColor !== 'rgba(0, 0, 0, 0)' && css.backgroundColor !== frame.backgroundColor
    };
}"""


def check_group(page, base, route, name):
    page.goto(base + "#/" + route, wait_until="domcontentloaded")
    group = page.get_by_role("group", name=name, exact=True)
    buttons = group.get_by_role("button")
    expect(buttons).to_have_count(2)
    for index in (0, 1):
        button = buttons.nth(index)
        if index:
            buttons.first.focus()
            page.keyboard.press("Tab")
            expect(button).to_be_focused()
            assert button.evaluate("""e => e.matches(':focus-visible') &&
                (getComputedStyle(e).outlineStyle !== 'none' || getComputedStyle(e).boxShadow !== 'none')"""), name
            page.keyboard.press("Space")
        expect(button).to_have_attribute("aria-pressed", "true")
        expect(group.locator('[aria-pressed="true"]')).to_have_count(1)
        m = button.evaluate(MEASURE)
        detail = (name, index, page.viewport_size, m)
        assert m["painted"] and m["side"] > 0, detail
        for distance in (m["top"], m["bottom"]):
            assert isclose(m["side"], distance, abs_tol=0.25), detail
        for outer, inner in m["curves"]:
            assert isclose(outer - inner, m["side"], abs_tol=0.25), detail
            if route == "reports":
                assert isclose(outer, m["height"] / 2, abs_tol=0.25), detail
            else:
                assert 0 < outer < m["height"] / 2, detail


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("url", nargs="?", default="http://127.0.0.1:5173/v4/")
    base = parser.parse_args().url.split("#", 1)[0]
    with sync_playwright() as driver:
        browser = driver.chromium.launch(channel="chrome", args=["--no-proxy-server"])
        for width in (390, 1440):
            page = browser.new_page(viewport={"width": width, "height": 844}, reduced_motion="reduce")
            check_group(page, base, "reports", "리포트 유형")
            check_group(page, base, "positions", "포지션 상태")
            page.close()
        browser.close()
    print("Report and position segments aligned at 390px and 1440px.")
