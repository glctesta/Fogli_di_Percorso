"""Entry point per `flask run` e Waitress."""
from fdp_app import create_app

app = create_app()


if __name__ == "__main__":
    # host=0.0.0.0 espone l'app a tutta la LAN. OK per test interno aziendale.
    # In produzione usare Waitress dietro IIS+HTTPS (vedi docs/install.md):
    #   .venv\Scripts\waitress-serve --host=0.0.0.0 --port=5010 app:app
    app.run(host="0.0.0.0", port=5010, debug=False)
