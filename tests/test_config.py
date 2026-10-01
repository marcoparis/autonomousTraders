import pytest

from backend.config import TRADERS, load_config


def test_project_config_is_valid():
    names = [t.name for t in TRADERS]
    assert names == ["Alpha", "Beta", "Gamma"]
    assert all(t.strategy and t.model for t in TRADERS)


def test_model_falls_back_to_default(tmp_path):
    cfg = tmp_path / "t.toml"
    cfg.write_text('initial_balance = 500\n[[trader]]\nname = "Solo"\nmodel = "gemini-3.5-flash-lite"\n'
                   '[[trader]]\nname = "Due"\n', encoding="utf-8")
    balance, traders = load_config(cfg)
    assert balance == 500
    assert traders[0].model == "gemini-3.5-flash-lite"
    assert traders[1].model  # default from TRADER_MODEL


@pytest.mark.parametrize("content", ['', '[[trader]]\nprofile = "x"\n', '[[trader]]\nname="A"\n[[trader]]\nname="a"\n'])
def test_invalid_configs_are_rejected(tmp_path, content):
    cfg = tmp_path / "bad.toml"
    cfg.write_text(content, encoding="utf-8")
    with pytest.raises(ValueError):
        load_config(cfg)
