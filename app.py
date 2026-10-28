

import calendar
import secrets
from pprint import pprint
from flask import flash, url_for
from datetime import datetime
import os

print("APP:", os.path.abspath(__file__))
from flask import Flask, redirect, render_template, request, send_from_directory, redirect, send_file

from werkzeug.utils import secure_filename

from database import get_connection, initialize_database

from flask import (
    Flask,
    render_template,
    request,
    redirect,
    session,
    flash,
    url_for
)

from flask import abort

from functools import wraps

from database import get_connection

app = Flask(__name__)
app.config["SECRET_KEY"] = "sei_torri_bike_manager_2026"
initialize_database()

def is_admin():
    return session.get("ruolo") == "ADMIN"


def admin_required(f):

    @wraps(f)
    def decorated_function(*args, **kwargs):

        if session.get("ruolo") != "ADMIN":
            abort(403)

        return f(*args, **kwargs)

    return decorated_function

@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        username = request.form["username"].strip().lower()
        password = request.form["password"]

        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT *
            FROM utenti
            WHERE username = ?
              AND password = ?
        """, (
            username.lower(),
            password
        ))
      

        utente = cursor.fetchone()

        print("USERNAME:", username)
        print("PASSWORD:", password)
        print("UTENTE:", utente)

        conn.close()

        if utente:

            session["utente_id"] = utente["id"]
            session["username"] = utente["username"]
            session["ruolo"] = utente["ruolo"]
            session["socio_id"] = utente["socio_id"]

            return redirect(url_for("dashboard"))

        flash(
            "Credenziali non valide",
            "danger"
        )

    return render_template("login.html")

print("LOGIN REGISTRATA")
#print("UTENTE LOGGATO:", session["username"])
#print("RUOLO:", session["ruolo"])
#print("SOCIO:", session["socio_id"])

@app.route("/logout")
def logout():

    session.clear()

    return redirect(url_for("login"))


def login_required(f):

    @wraps(f)
    def decorated_function(*args, **kwargs):

        if "utente_id" not in session:
            return redirect("/login")

        return f(*args, **kwargs)

    return decorated_function

@app.route("/profilo")
@login_required
def profilo():

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT *
        FROM utenti
        WHERE id = ?
    """, (
        session["utente_id"],
    ))

    utente = cursor.fetchone()

    conn.close()

    return render_template(
        "profilo.html",
        utente=utente
    )

@app.route("/profilo/aggiorna", methods=["POST"])
@login_required
def aggiorna_profilo():

    username = request.form["username"]
    password = request.form["password"]

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE utenti
        SET
            username = ?,
            password = ?
        WHERE id = ?
    """, (
        username,
        password,
        session["utente_id"]
    ))

    conn.commit()
    conn.close()

    session["username"] = username

    flash(
        "Profilo aggiornato correttamente.",
        "success"
    )

    return redirect("/profilo")

@app.route("/profilo/aggiorna_password", methods=["POST"])
@login_required
def aggiorna_password():

    nuova_password = request.form["password"]

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE utenti
        SET password = ?
        WHERE id = ?
    """, (
        nuova_password,
        session["utente_id"]
    ))

    conn.commit()
    conn.close()

    flash(
        "Password aggiornata correttamente.",
        "success"
    )

    return redirect("/profilo")

def admin_required(f):

    @wraps(f)
    def decorated_function(*args, **kwargs):

        if session.get("ruolo") != "ADMIN":
            flash(
                "Accesso consentito solo agli amministratori.",
                "danger"
            )
            return redirect(url_for("dashboard"))

        return f(*args, **kwargs)

    return decorated_function

@app.route("/utenti")
@login_required
@admin_required
def utenti():

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            u.*,
            s.nome,
            s.cognome
        FROM utenti u
        LEFT JOIN soci s
            ON s.id = u.socio_id
        ORDER BY u.username
    """)

    utenti = cursor.fetchall()

    conn.close()

    return render_template(
        "utenti.html",
        utenti=utenti
    )


@app.route("/utenti/modifica/<int:id>")
@login_required
@admin_required
def modifica_utente(id):

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT *
        FROM utenti
        WHERE id = ?
    """, (id,))
    utente = cursor.fetchone()

    cursor.execute("""
        SELECT *
        FROM soci
        ORDER BY cognome, nome
    """)
    soci = cursor.fetchall()

    conn.close()

    return render_template(
        "modifica_utente.html",
        utente=utente,
        soci=soci
    )



@app.route("/utenti/aggiorna/<int:id>", methods=["POST"])
@login_required
@admin_required
def aggiorna_utente(id):

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE utenti
        SET
            username = ?,
            password = ?,
            ruolo = ?,
            socio_id = ?
        WHERE id = ?
    """, (
        request.form["username"],
        request.form["password"],
        request.form["ruolo"],
        request.form["socio_id"] or None,
        id
    ))

    conn.commit()
    conn.close()

    flash("Utente aggiornato correttamente", "success")

    return redirect("/utenti")

@app.route("/partecipazioni")
@login_required
def partecipazioni():

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT *
        FROM gare
        ORDER BY data
    """)

    gare_db = cursor.fetchall()

    gare = {}

    for gara in gare_db:

        cursor.execute("""
            SELECT
                p.id,
                p.stato,
                p.gara_id,
                s.nome,
                s.cognome
            FROM partecipazioni p
            JOIN soci s
                ON s.id = p.socio_id
            WHERE p.gara_id = ?
            ORDER BY s.cognome, s.nome
        """, (gara["id"],))

        partecipanti = cursor.fetchall()

        stats = {
            "NON_INTERESSATO": 0,
            "INTERESSATO": 0,
            "CONFERMATO": 0,
            "PARTECIPATO": 0,
            "ASSENTE": 0
        }

        for p in partecipanti:
            if p["stato"] in stats:
                stats[p["stato"]] += 1

        gare[gara["id"]] = {
            "gara": gara,
            "partecipanti": partecipanti,
            "stats": stats
        }

    conn.close()

    from pprint import pprint
    pprint(gare)

    return render_template(
        "partecipazioni.html",
        gare=gare
    )

@app.route("/")
@login_required
def dashboard():

    oggi = datetime.now()

    anno = request.args.get(
        "anno",
        default=oggi.year,
        type=int
    )

    mese = request.args.get(
        "mese",
        default=oggi.month,
        type=int
    )

    calendario = calendar.monthcalendar(
    anno,
    mese
    )   

    mese_prec = mese - 1
    anno_prec = anno

    if mese_prec < 1:

        mese_prec = 12
        anno_prec -= 1

    mese_succ = mese + 1
    anno_succ = anno

    if mese_succ > 12:

        mese_succ = 1
        anno_succ += 1


    conn = get_connection()

    cursor = conn.cursor()

        # NUMERO GARE

    cursor.execute("""
    SELECT COUNT(*)
    FROM gare
    """)

    tot_gare = cursor.fetchone()[0]

    # NUMERO SOCI

    cursor.execute("""
    SELECT COUNT(*)
    FROM soci
    """)

    tot_soci = cursor.fetchone()[0]

    # NUMERO CIRCUITI

    cursor.execute("""
    SELECT COUNT(*)
    FROM circuiti
    """)

    tot_circuiti = cursor.fetchone()[0]

    # NUMERO PARTECIPAZIONI

    cursor.execute("""
    SELECT COUNT(*)
    FROM partecipazioni
    """)

    tot_partecipazioni = cursor.fetchone()[0]

    # =====================================
    # PROSSIME GARE
    # =====================================

    cursor.execute("""
    SELECT
        id,
        nome,
        data
    FROM gare
    ORDER BY data
    LIMIT 10
    """)

    prossime_gare = cursor.fetchall()

    # =====================================
    # GARE DEL MESE PER CALENDARIO
    # =====================================

    cursor.execute("""
    SELECT
        nome,
        data
    FROM gare
    WHERE substr(data,1,7)=?
    """, (
        f"{anno}-{str(mese).zfill(2)}",
    ))

    gare_mese = cursor.fetchall()

    gare_per_giorno = {}

    for gara in gare_mese:

        giorno = int(
            gara["data"].split("-")[2]
        )

        if giorno not in gare_per_giorno:

            gare_per_giorno[giorno] = []

        gare_per_giorno[giorno].append(
            gara["nome"]
        )

    print("GARE PER GIORNO:")
    print(gare_per_giorno)

    # =====================================
    # STATISTICHE PARTECIPAZIONI
    # =====================================

    cursor.execute("""
    SELECT COUNT(*)
    FROM partecipazioni
    WHERE stato='INTERESSATO'
    """)

    interessati = cursor.fetchone()[0]

    cursor.execute("""
    SELECT COUNT(*)
    FROM partecipazioni
    WHERE stato='CONFERMATO'
    """)

    confermati = cursor.fetchone()[0]

    cursor.execute("""
    SELECT COUNT(*)
    FROM partecipazioni
    WHERE stato='PARTECIPATO'
    """)

    partecipato = cursor.fetchone()[0]

    cursor.execute("""
    SELECT COUNT(*)
    FROM partecipazioni
    WHERE stato='ASSENTE'
    """)

    assenti = cursor.fetchone()[0]

    conn.close()

    return render_template(
    "dashboard.html",

    prossime_gare=prossime_gare,

    gare_per_giorno=gare_per_giorno,

    interessati=interessati,
    confermati=confermati,
    partecipato=partecipato,
    assenti=assenti,

    tot_gare=tot_gare,
    tot_soci=tot_soci,
    tot_circuiti=tot_circuiti,
    tot_partecipazioni=tot_partecipazioni,

    calendario=calendario,
    anno=anno,
    mese=mese,
    mese_prec=mese_prec,
    anno_prec=anno_prec,

    mese_succ=mese_succ,
    anno_succ=anno_succ,
)

@app.route('/gare/<int:gara_id>/partecipazioni')
@login_required
def modifica_partecipazioni_gara(gara_id):

    conn = get_connection()
    cursor = conn.cursor()

    # Gara
    cursor.execute("""
        SELECT *
        FROM gare
        WHERE id = ?
    """, (gara_id,))
    gara = cursor.fetchone()

    # Partecipazioni
    cursor.execute("""
        SELECT
            p.id,
            p.gara_id,
            p.socio_id,
            p.stato,
            s.nome,
            s.cognome
        FROM partecipazioni p
        JOIN soci s ON p.socio_id = s.id
        WHERE p.gara_id = ?
        ORDER BY s.cognome, s.nome
    """, (gara_id,))

    partecipazioni = cursor.fetchall()

    conn.close()

    return render_template(
        'partecipazioni_gara.html',
        gara=gara,
        partecipazioni=partecipazioni
    )

@app.route("/gare")
@login_required
def gare():

    conn = get_connection()

    cursor = conn.cursor()

    cursor.execute("""
    SELECT
        id,
        nome,
        luogo,
        data,
        tipologia,
        circuito,
        distanza,
        dislivello,
        descrizione
    FROM gare
    ORDER BY data
    """)

    gare = cursor.fetchall()

    gare_con_statistiche = []

    for gara in gare:

        cursor.execute("""
        SELECT
            stato,
            COUNT(*) AS totale
        FROM partecipazioni
        WHERE gara_id = ?
        GROUP BY stato
        """, (
            gara["id"],
        ))

        stats = {
            "NON_INTERESSATO": 0,
            "INTERESSATO": 0,
            "CONFERMATO": 0,
            "PARTECIPATO": 0,
            "ASSENTE": 0
        }

        for row in cursor.fetchall():

            stats[row["stato"]] = row["totale"]

        gare_con_statistiche.append({
            "gara": gara,
            "stats": stats
        })

    conn.close()

    return render_template(
        "gare.html",
        gare=gare_con_statistiche
    )

@app.route("/gare/allegati/<int:gara_id>")
@login_required
def allegati_gara(gara_id):

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT *
    FROM gare
    WHERE id = ?
    """, (
        gara_id,
    ))

    gara = cursor.fetchone()

    cursor.execute("""
    SELECT *
    FROM allegati_gare
    WHERE gara_id = ?
    ORDER BY nome_file
    """, (
        gara_id,
    ))

    allegati = cursor.fetchall()

    conn.close()

    return render_template(
        "allegati_gara.html",
        gara=gara,
        allegati=allegati
    )



@app.route("/gare/<int:gara_id>")
@login_required
def dettaglio_gara(gara_id):

    conn = get_connection()
    cursor = conn.cursor()

    # Gara
    cursor.execute("""
        SELECT *
        FROM gare
        WHERE id=?
    """, (gara_id,))
    gara = cursor.fetchone()

    # Partecipazioni
    cursor.execute("""
        SELECT
            s.id as socio_id,
            s.nome,
            s.cognome,
            p.id as id,
            COALESCE(p.stato,'NON_INTERESSATO') as stato
        FROM soci s
        LEFT JOIN partecipazioni p
            ON s.id = p.socio_id
            AND p.gara_id = ?
        ORDER BY s.cognome, s.nome
    """, (gara_id,))
    partecipanti = cursor.fetchall()

    # Contatori stati
    cursor.execute("""
        SELECT stato, COUNT(*) as totale
        FROM partecipazioni
        WHERE gara_id=?
        GROUP BY stato
    """, (gara_id,))
    conteggi = cursor.fetchall()

    conn.close()

    return render_template(
        "dettaglio_gara.html",
        gara=gara,
        partecipanti=partecipanti,
        conteggi=conteggi
    )

@app.route(
    "/gare/allegati/upload/<int:gara_id>",
    methods=["POST"]
)
def upload_allegato(gara_id):

    file = request.files["file"]

    if file.filename == "":
        return redirect(
            f"/gare/allegati/{gara_id}"
        )

    os.makedirs(    
        "uploads",
        exist_ok=True
    )

    percorso = os.path.join(
        "uploads",
        file.filename
    )

    file.save(percorso)

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    INSERT INTO allegati_gare
    (
        gara_id,
        nome_file,
        percorso_file
    )
    VALUES (?, ?, ?)
    """, (
        gara_id,
        file.filename,
        percorso
    ))

    conn.commit()
    conn.close()

    return redirect(
        f"/gare/allegati/{gara_id}"
    )


@app.route("/allegati/download/<int:allegato_id>")
@login_required
def download_allegato(allegato_id):

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT *
    FROM allegati_gare
    WHERE id = ?
    """, (
        allegato_id,
    ))

    allegato = cursor.fetchone()

    conn.close()

    return send_from_directory(
        "uploads",
        allegato["nome_file"],
        as_attachment=True
    )

@app.route("/allegati/elimina/<int:allegato_id>")
@login_required
def elimina_allegato(allegato_id):

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT *
    FROM allegati_gare
    WHERE id = ?
    """, (
        allegato_id,
    ))

    allegato = cursor.fetchone()

    if allegato:

        if os.path.exists(
            allegato["percorso_file"]
        ):
            os.remove(
                allegato["percorso_file"]
            )

        gara_id = allegato["gara_id"]

        cursor.execute("""
        DELETE FROM allegati_gare
        WHERE id = ?
        """, (
            allegato_id,
        ))

        conn.commit()

    else:

        gara_id = 0

    conn.close()

    return redirect(
        f"/gare/allegati/{gara_id}"
    )

@app.route("/soci/allegati/<int:socio_id>")
@login_required
def allegati_socio(socio_id):

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT *
    FROM soci
    WHERE id = ?
    """, (
        socio_id,
    ))

    socio = cursor.fetchone()

    cursor.execute("""
    SELECT *
    FROM allegati_soci
    WHERE socio_id = ?
    ORDER BY nome_file
    """, (
        socio_id,
    ))

    allegati = cursor.fetchall()

    conn.close()

    return render_template(
        "allegati_socio.html",
        socio=socio,
        allegati=allegati
    )

@app.route("/circuiti/allegati/<int:id>")
@login_required
def allegati_circuito(id):

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT * FROM circuiti WHERE id=?",
        (id,)
    )

    circuito = cursor.fetchone()

    cursor.execute(
        "SELECT * FROM allegati_circuiti WHERE circuito_id=?",
        (id,)
    )

    allegati = cursor.fetchall()

    conn.close()

    return render_template(
        "allegati_circuito.html",
        circuito=circuito,
        allegati=allegati
    )

@app.route(
    "/circuiti/allegati/upload/<int:id>",
    methods=["POST"]
)
@login_required
def upload_allegato_circuito(id):

    file = request.files["file"]

    if file.filename == "":
        return redirect(f"/circuiti/allegati/{id}")

    nome_file = secure_filename(
        file.filename
    )

    percorso = os.path.join(
        "uploads",
        "circuiti",
        nome_file
    )

    file.save(percorso)

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    INSERT INTO allegati_circuiti
    (
        circuito_id,
        nome_file,
        percorso_file
    )
    VALUES (?, ?, ?)
    """, (
        id,
        nome_file,
        percorso
    ))

    conn.commit()
    conn.close()

    return redirect(f"/circuiti/allegati/{id}")

@app.route("/gare/allegati/elimina/<int:allegato_id>")
@login_required
def elimina_allegato_gara(allegato_id):

    import os

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT *
    FROM allegati_gare
    WHERE id = ?
    """, (
        allegato_id,
    ))

    allegato = cursor.fetchone()

    if allegato is None:

        conn.close()

        return redirect("/gare")

    gara_id = allegato["gara_id"]

    if os.path.exists(
        allegato["percorso_file"]
    ):
        os.remove(
            allegato["percorso_file"]
        )

    cursor.execute("""
    DELETE FROM allegati_gare
    WHERE id = ?
    """, (
        allegato_id,
    ))

    conn.commit()
    conn.close()

    return redirect(
        f"/gare/allegati/{gara_id}"
    )

from flask import send_file

@app.route("/gare/allegati/download/<int:id>")
@login_required
def download_allegato_gara(id):

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT *
    FROM allegati_gare
    WHERE id=?
    """, (
        id,
    ))

    allegato = cursor.fetchone()

    conn.close()

    return send_file(
        allegato["percorso_file"],
        as_attachment=True
    )

@app.route("/soci/allegati/download/<int:id>")
@login_required
def download_allegato_socio(id):

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT *
    FROM allegati_soci
    WHERE id=?
    """, (
        id,
    ))

    allegato = cursor.fetchone()

    conn.close()

    return send_file(
        allegato["percorso_file"],
        as_attachment=True
    )

@app.route("/soci/allegati/elimina/<int:id>")
def elimina_allegato_socio(id):

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT *
    FROM allegati_soci
    WHERE id=?
    """, (
        id,
    ))

    allegato = cursor.fetchone()

    socio_id = allegato["socio_id"]

    if os.path.exists(
        allegato["percorso_file"]
    ):
        os.remove(
            allegato["percorso_file"]
        )

    cursor.execute("""
    DELETE FROM allegati_soci
    WHERE id=?
    """, (
        id,
    ))

    conn.commit()
    conn.close()

    return redirect(
        f"/soci/allegati/{socio_id}"
    )

@app.route("/circuiti/allegati/download/<int:id>")
def download_allegato_circuito(id):

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT *
    FROM allegati_circuiti
    WHERE id=?
    """, (
        id,
    ))

    allegato = cursor.fetchone()

    conn.close()

    return send_file(
        allegato["percorso_file"],
        as_attachment=True
    )

@app.route("/circuiti/allegati/elimina/<int:id>")
def elimina_allegato_circuito(id):

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT *
    FROM allegati_circuiti
    WHERE id=?
    """, (
        id,
    ))

    allegato = cursor.fetchone()

    circuito_id = allegato["circuito_id"]

    if os.path.exists(
        allegato["percorso_file"]
    ):
        os.remove(
            allegato["percorso_file"]
        )

    cursor.execute("""
    DELETE FROM allegati_circuiti
    WHERE id=?
    """, (
        id,
    ))

    conn.commit()
    conn.close()

    return redirect(
        f"/circuiti/allegati/{circuito_id}"
    )


@app.route(
    "/soci/allegati/upload/<int:socio_id>",
    methods=["POST"]
)
def upload_allegato_socio(socio_id):

    import os

    file = request.files["file"]

    if not file:
        return redirect(
            f"/soci/allegati/{socio_id}"
        )

    os.makedirs(
        "uploads",
        exist_ok=True
    )

    percorso = os.path.join(
        "uploads",
        file.filename
    )

    file.save(percorso)

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    INSERT INTO allegati_soci
    (
        socio_id,
        nome_file,
        percorso_file
    )
    VALUES (?, ?, ?)
    """, (
        socio_id,
        file.filename,
        percorso
    ))

    conn.commit()
    conn.close()

    return redirect(
        f"/soci/allegati/{socio_id}"
    )


@app.route("/soci")
def soci():

    conn = get_connection()

    cursor = conn.cursor()

    cursor.execute("""
    SELECT *
    FROM soci
    ORDER BY cognome, nome
    """)

    soci = cursor.fetchall()

    conn.close()

    return render_template(
        "soci.html",
        soci=soci
    )



@app.route("/soci/salva", methods=["POST"])
def salva_socio():

    nome = request.form["nome"]
    cognome = request.form["cognome"]
    telefono = request.form["telefono"]
    email = request.form["email"]
    categoria = request.form["categoria"]
    note = request.form["note"]

    conn = get_connection()

    cursor = conn.cursor()

    cursor.execute("""
    INSERT INTO soci
    (
        nome,
        cognome,
        telefono,
        email,
        categoria,
        note
    )
    VALUES (?, ?, ?, ?, ?, ?)
    """, (
        nome,
        cognome,
        telefono,
        email,
        categoria,
        note
    ))

    conn.commit()
    conn.close()

    return redirect("/soci")

@app.route("/soci/nuovo")
def nuovo_socio():

    return render_template(
        "nuovo_socio.html"
    )



@app.route('/partecipazioni/aggiorna_stato', methods=['POST'])
def aggiorna_stato_partecipazione():

    partecipazione_id = request.form['partecipazione_id']
    stato = request.form['stato']

    conn = get_connection()
    cursor = conn.cursor()

    # Recupero dati partecipazione corrente
    cursor.execute("""
        SELECT
            p.socio_id,
            p.gara_id,
            g.data
        FROM partecipazioni p
        JOIN gare g ON p.gara_id = g.id
        WHERE p.id = ?
    """, (partecipazione_id,))

    partecipazione = cursor.fetchone()

    # ==================================================
    # CONTROLLO PERMESSI
    # ==================================================

    if session.get("ruolo") != "ADMIN":

        if partecipazione["socio_id"] != session.get("socio_id"):

            conn.close()

            flash(
                "Non è possibile modificare la partecipazione di un altro socio.",
                "warning"
            )

            return redirect(url_for("partecipazioni"))

    socio_id = partecipazione["socio_id"]
    gara_id = partecipazione["gara_id"]
    data_gara = partecipazione["data"]

    # BLOCCO DOPPIA CONFERMA
    if stato in ("CONFERMATO", "PARTECIPATO"):

        cursor.execute("""
            SELECT
                g.nome,
                g.data,
                p.stato
            FROM partecipazioni p
            JOIN gare g ON p.gara_id = g.id
            WHERE p.socio_id = ?
              AND p.id <> ?
              AND g.data = ?
              AND p.stato IN ('CONFERMATO','PARTECIPATO')
        """, (
            socio_id,
            partecipazione_id,
            data_gara
        ))

        conflitto = cursor.fetchone()

        if conflitto:

            flash(
                f"Impossibile confermare: anche se sappiamo quanto sei forte, risulti già "
                f"{conflitto['stato']} nella gara "
                f"'{conflitto['nome']}' del {conflitto['data']}.",
                "danger"
            )

            conn.close()

            return redirect(
                url_for(
                    "dettaglio_gara",
                    gara_id=gara_id
                )
            )

    # Aggiornamento stato
    cursor.execute("""
        UPDATE partecipazioni
        SET stato = ?
        WHERE id = ?
    """, (
        stato,
        partecipazione_id
    ))

    conn.commit()
    conn.close()

    return redirect(
        url_for(
            "dettaglio_gara",
            gara_id=gara_id
        )
    )

@app.route('/partecipazioni/aggiorna_stato_part', methods=['POST'])
def aggiorna_stato_partecipazione_part():

    partecipazione_id = request.form['partecipazione_id']
    stato = request.form['stato']

    conn = get_connection()
    cursor = conn.cursor()

    # Recupero dati partecipazione corrente
    cursor.execute("""
        SELECT
            p.socio_id,
            p.gara_id,
            g.data
        FROM partecipazioni p
        JOIN gare g ON p.gara_id = g.id
        WHERE p.id = ?
    """, (partecipazione_id,))

    partecipazione = cursor.fetchone()

    if session.get("ruolo") != "ADMIN":

         if partecipazione["socio_id"] != session.get("socio_id"):

            conn.close()

            flash(
                "Puoi modificare solo le tue partecipazioni alle gare.",
                "warning"
            )

            return redirect(url_for("partecipazioni"))

    socio_id = partecipazione["socio_id"]
    gara_id = partecipazione["gara_id"]
    data_gara = partecipazione["data"]

    # BLOCCO DOPPIA CONFERMA
    if stato in ("CONFERMATO", "PARTECIPATO"):

        cursor.execute("""
            SELECT
                g.nome,
                g.data,
                p.stato
            FROM partecipazioni p
            JOIN gare g ON p.gara_id = g.id
            WHERE p.socio_id = ?
              AND p.id <> ?
              AND g.data = ?
              AND p.stato IN ('CONFERMATO','PARTECIPATO')
        """, (
            socio_id,
            partecipazione_id,
            data_gara
        ))

        conflitto = cursor.fetchone()

        if conflitto:

            flash(
                f"Impossibile confermare: anche se sappiamo quanto sei forte, risulti già "
                f"{conflitto['stato']} nella gara "
                f"'{conflitto['nome']}' del {conflitto['data']}.",
                "danger"
            )

            conn.close()

            return redirect(
                url_for(
                    "partecipazioni",
                    gara_id=gara_id
                )
            )

    # Aggiornamento stato
    cursor.execute("""
        UPDATE partecipazioni
        SET stato = ?
        WHERE id = ?
    """, (
        stato,
        partecipazione_id
    ))

    conn.commit()
    conn.close()

    return redirect(
        url_for(
            "partecipazioni",
            gara_id=gara_id
        )
    )

@app.route("/circuiti")
def circuiti():

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT *
    FROM circuiti
    ORDER BY nome
    """)

    circuiti = cursor.fetchall()

    conn.close()

    return render_template(
        "circuiti.html",
        circuiti=circuiti
    )

@app.route("/circuiti/nuovo")
def nuovo_circuito():

    return render_template(
        "nuovo_circuito.html"
    )

@app.route("/circuiti/salva", methods=["POST"])
def salva_circuito():

    nome = request.form["nome"]

    conn = get_connection()

    cursor = conn.cursor()

    cursor.execute("""
    INSERT INTO circuiti
    (
        nome
    )
    VALUES (?)
    """, (
        nome,
    ))

    conn.commit()
    conn.close()

    return redirect("/circuiti")

@app.route("/circuiti/modifica/<int:id>")
def modifica_circuito(id):

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT *
    FROM circuiti
    WHERE id=?
    """, (
        id,
    ))

    circuito = cursor.fetchone()

    conn.close()

    return render_template(
        "modifica_circuito.html",
        circuito=circuito
    )

@app.route(
    "/circuiti/aggiorna/<int:id>",
    methods=["POST"]
)
def aggiorna_circuito(id):

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    UPDATE circuiti
    SET
        nome=?
    WHERE id=?
    """, (

        request.form["nome"],
        id

    ))

    conn.commit()
    conn.close()

    return redirect("/circuiti")

@app.route("/circuiti/elimina/<int:circuito_id>")
def elimina_circuito(circuito_id):

    conn = get_connection()

    cursor = conn.cursor()

    cursor.execute("""
    DELETE FROM circuiti
    WHERE id = ?
    """, (
        circuito_id,
    ))

    conn.commit()

    conn.close()

    return redirect("/circuiti")

@app.route("/calendario")
def calendario():

    oggi = datetime.now()

    anno = request.args.get(
        "anno",
        default=oggi.year,
        type=int
    )

    mese = request.args.get(
        "mese",
        default=oggi.month,
        type=int
    )

    conn = get_connection()

    cursor = conn.cursor()

    cursor.execute("""
    SELECT
        nome,
        data
    FROM gare
    WHERE substr(data,1,7)=?
    """, (
        f"{anno}-{str(mese).zfill(2)}",
    ))

    gare_mese = cursor.fetchall()
    print("GARE MESE:")
    for g in gare_mese:
        print(dict(g))

    gare_per_giorno = {}

    for gara in gare_mese:

        data_gara = gara["data"]

        giorno = int(data_gara.split("-")[2])

        if giorno not in gare_per_giorno:

            gare_per_giorno[giorno] = []

        gare_per_giorno[giorno].append(
            gara["nome"]
        )
        print("GARE PER GIORNO:")
        print(gare_per_giorno)

    calendario = calendar.monthcalendar(
        anno,
        mese
    )

    mese_prec = mese - 1
    anno_prec = anno

    if mese_prec < 1:
        mese_prec = 12
        anno_prec -= 1

    mese_succ = mese + 1
    anno_succ = anno

    if mese_succ > 12:
        mese_succ = 1
        anno_succ += 1

    conn.close()

    return render_template(
        "calendario.html",
        calendario=calendario,
        anno=anno,
        mese=mese,
        mese_prec=mese_prec,
        anno_prec=anno_prec,
        mese_succ=mese_succ,
        anno_succ=anno_succ,
        gare_mese=gare_mese,
        gare_per_giorno=gare_per_giorno
    )

@app.route("/gare/nuova")
def nuova_gara():

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT nome
    FROM circuiti
    ORDER BY nome
    """)

    circuiti = cursor.fetchall()

    conn.close()

    return render_template(
        "nuova_gara.html",
        circuiti=circuiti
    )

@app.route("/gare/salva", methods=["POST"])
def salva_gara():

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    INSERT INTO gare
    (
        nome,
        luogo,
        data,
        tipologia,
        circuito,
        distanza,
        dislivello,
        descrizione
    )
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    RETURNING id
    """, (

        request.form["nome"],
        request.form["luogo"],
        request.form["data"],
        request.form["tipologia"],
        request.form["circuito"],
        request.form["distanza"],
        request.form["dislivello"],
        request.form["descrizione"]

    ))

    gara_id = cursor.fetchone()["id"]
    conn.commit()

    cursor.execute("""
    SELECT id
    FROM soci
    """)

    soci = cursor.fetchall()

    for socio in soci:

        cursor.execute("""
        INSERT INTO partecipazioni
        (
            socio_id,
            gara_id,
            stato
        )
        VALUES (?, ?, ?)
        """, (
            socio["id"],
            gara_id,
            "NON_INTERESSATO"
        ))

    conn.commit()
    conn.close()

    return redirect("/gare")

@app.route("/gare/elimina/<int:id>")
def elimina_gara(id):

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        "DELETE FROM gare WHERE id=?",
        (id,)
    )

    conn.commit()
    conn.close()

    return redirect("/gare")

@app.route("/gare/modifica/<int:id>")
def modifica_gara(id):

    conn = get_connection()

    cursor = conn.cursor()

    cursor.execute("""
    SELECT *
    FROM gare
    WHERE id=?
    """, (
        id,
    ))

    gara = cursor.fetchone()

    cursor.execute("""
    SELECT nome
    FROM circuiti
    ORDER BY nome
    """)

    circuiti = cursor.fetchall()

    conn.close()

    return render_template(
        "modifica_gara.html",
        gara=gara,
        circuiti=circuiti
    )

@app.route("/gare/aggiorna/<int:id>", methods=["POST"])
def aggiorna_gara(id):

    conn = get_connection()

    cursor = conn.cursor()

    cursor.execute("""
    UPDATE gare
    SET
        nome=?,
        luogo=?,
        data=?,
        tipologia=?,
        circuito=?,
        distanza=?,
        dislivello=?,
        descrizione=?
    WHERE id=?
    """, (

        request.form["nome"],
        request.form["luogo"],
        request.form["data"],
        request.form["tipologia"],
        request.form["circuito"],
        request.form["distanza"],
        request.form["dislivello"],
        request.form["descrizione"],
        id

    ))

    conn.commit()
    conn.close()

    return redirect("/gare")

@app.route("/soci/modifica/<int:socio_id>")
@login_required
def modifica_socio(socio_id):

    # I soci possono modificare solo se stessi
    if session.get("ruolo") == "SOCIO":

        if socio_id != session.get("socio_id"):

            flash(
                "Puoi modificare solo la tua anagrafica.",
                "warning"
            )

            return redirect(url_for("soci"))

    conn = get_connection()

    cursor = conn.cursor()

    cursor.execute("""
    SELECT *
    FROM soci
    WHERE id=?
    """, (
        socio_id,
    ))

    socio = cursor.fetchone()

    conn.close()

    return render_template(
        "modifica_socio.html",
        socio=socio
    )

@app.route("/soci/aggiorna/<int:id>", methods=["POST"])
@login_required
def aggiorna_socio(id):

    if session.get("ruolo") == "SOCIO":

        if id != session.get("socio_id"):

            flash(
                "Puoi aggiornare solo la tua anagrafica.",
                "warning"
            )

            return redirect(url_for("dashboard"))

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    UPDATE soci
    SET
        nome=?,
        cognome=?,
        telefono=?,
        email=?,
        categoria=?,
        note=?
    WHERE id=?
    """, (

        request.form["nome"],
        request.form["cognome"],
        request.form["telefono"],
        request.form["email"],
        request.form["categoria"],
        request.form["note"],
        id

    ))

    conn.commit()
    conn.close()

    return redirect("/soci")

@app.route("/soci/elimina/<int:id>")
def elimina_socio(id):

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        "DELETE FROM partecipazioni WHERE socio_id=?",
        (id,)
    )

    cursor.execute(
        "DELETE FROM soci WHERE id=?",
        (id,)
    )

    conn.commit()
    conn.close()

    return redirect("/soci")

@app.route(
    "/gare/allegati/upload/<int:id>",
    methods=["POST"]
)
def upload_allegato_gara(id):

    file = request.files["file"]

    if file.filename == "":
        return redirect(f"/gare/allegati/{id}")

    nome_file = secure_filename(
        file.filename
    )

    percorso = os.path.join(
        "uploads",
        "gare",
        nome_file
    )

    file.save(percorso)

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    INSERT INTO allegati_gare
    (
        gara_id,
        nome_file,
        percorso_file
    )
    VALUES (?, ?, ?)
    """, (
        id,
        nome_file,
        percorso
    ))

    conn.commit()
    conn.close()

    return redirect(f"/gare/allegati/{id}")




def login_required(f):

    @wraps(f)
    def decorated_function(*args, **kwargs):

        if "utente_id" not in session:
            return redirect("/login")

        return f(*args, **kwargs)

    return decorated_function

print(app.url_map)


if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=5000,
        debug=True
    )

