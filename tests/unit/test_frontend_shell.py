from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_netlify_shell_uses_relative_assets() -> None:
    html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
    assert 'href="css/app.css"' in html
    assert 'src="config.js"' in html
    assert 'src="js/app.js"' in html
    assert "url_for" not in html
    assert (ROOT / "web" / "css" / "app.css").is_file()
    assert (ROOT / "web" / "js" / "app.js").is_file()
    assert (ROOT / "netlify.toml").is_file()
