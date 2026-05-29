import streamlit as st
import pandas as pd
import psycopg2
import secrets  # Module de sécurité pour la création de clés cryptographiques
import io       # Pour la gestion du tampon mémoire Excel
import os       # REQUIS : Pour permettre à Docker de communiquer ses variables réseau
from kafka import KafkaAdminClient
from streamlit_autorefresh import st_autorefresh  # Import de l'auto-rafraîchissement

# --- INTERCONNEXION DYNAMIQUE (DOCKER / LOCAL) ---
# Si le conteneur tourne sous Docker, il lira 'postgres_db'. Sinon, il se rabat sur 'localhost'
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_NAME = os.getenv("DB_NAME", "tfc_fraud_db")
DB_USER = os.getenv("DB_USER", "admin")
DB_PASS = os.getenv("DB_PASS", "MonSuperPassword2026")

DB_URI = f"dbname={DB_NAME} user={DB_USER} password={DB_PASS} host={DB_HOST} port=5432"

# Configuration esthétique globale (Titre épuré et mise en page large)
st.set_page_config(page_title="Supervision Anti-Fraude", layout="wide", page_icon="🛡️")

# ==========================================
# SYSTÈME D'AUTHENTIFICATION (SESSION STATE)
# ==========================================
if "authentifie" not in st.session_state:
    st.session_state["authentifie"] = False

def verifier_identifiants(id_admin, cle_admin):
    """Vérifie dans PostgreSQL si l'ID et la clé correspondent exclusivement à un Admin"""
    try:
        conn = psycopg2.connect(DB_URI)
        cursor = conn.cursor()
        # Contrôle d'accès strict sur le rôle 'Admin'
        cursor.execute("""
            SELECT id_client FROM UTILISATEUR 
            WHERE id_client = %s AND api_key = %s AND role = 'Admin';
        """, (id_admin, cle_admin))
        
        resultat = cursor.fetchone()
        cursor.close()
        conn.close()
        return resultat is not None
    except Exception as e:
        # Solution de secours manuelle si l'infrastructure PostgreSQL est en cours de démarrage
        if str(id_admin) == "100" and cle_admin == "admin_master_key_2026":
            return True
        return False

# --- ÉCRAN DE VERROUILLAGE ---
if not st.session_state["authentifie"]:
    st.markdown("<br><br>", unsafe_allow_html=True)
    st.markdown("<h1 style='text-align: center;'>🛡️ Accès Sécurisé - Supervision</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; color: gray;'>Veuillez valider vos privilèges administratifs pour continuer.</p>", unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 1.5, 1])
    with col2:
        with st.form("Formulaire de Connexion", clear_on_submit=False):
            st.subheader(" Authentification Requise")
            id_input = st.number_input("Identifiant Unique Administrateur", min_value=1, step=1, value=100)
            key_input = st.text_input("Clé d'accès Maître (API Key)", type="password")
            st.caption(" Astuce TFC : admin_master_key_2026 pour le mode secours.")
            bouton_connexion = st.form_submit_button("🔓 Déverrouiller la console")
            
            if bouton_connexion:
                if verifier_identifiants(id_input, key_input):
                    st.session_state["authentifie"] = True
                    st.success("Connexion établie. Initialisation du tableau de bord...")
                    st.rerun()
                else:
                    st.error("Échec de l'authentification : Identifiants incorrects ou rôle insuffisant.")
    st.stop()  # Interrompt l'exécution pour bloquer le reste des composants de l'interface

# ==========================================
# APPLICATION PRINCIPALE (UNIQUEMENT SI AUTHENTIFIÉ)
# ==========================================

st.title("🛡️ Supervision Anti-Fraude Système")

# CONFIGURATION DU RAFRAÎCHISSEMENT AUTOMATIQUE (Toutes les 2 secondes)
st_autorefresh(interval=2000, limit=None, key="rafraichissement_ia_auto_final")

# Initialisation de la clé dans la mémoire de session
if "cle_securisee" not in st.session_state:
    st.session_state["cle_securisee"] = ""

# ==========================================
# BARRE LATÉRALE : MODULE DE SUPPRESSION & DECONNEXION
# ==========================================
with st.sidebar:
    st.header("👤 Session Administrateur")
    st.caption("Statut : **En ligne**")
    if st.button(" Fermer la session"):
        st.session_state["authentifie"] = False
        st.rerun()
        
    st.markdown("---")
    st.header(" Gestion des Révocations")
    st.subheader("Supprimer un Tenant Existant")
    
    conn_sidebar = None
    try:
        conn_sidebar = psycopg2.connect(DB_URI)
        # On extrait la liste des clients en excluant l'admin (100) pour empêcher une auto-suppression fatale
        df_delete = pd.read_sql_query("SELECT id_client FROM UTILISATEUR WHERE id_client != 100 ORDER BY id_client ASC;", conn_sidebar)
        liste_ids = df_delete['id_client'].tolist()
        
        with st.form("Formulaire Suppression", clear_on_submit=True):
            id_cible = st.selectbox("Sélectionner l'ID du client à révoquer", liste_ids if liste_ids else ["Aucun"])
            bouton_supprimer = st.form_submit_button(" Révoquer l'accès")
            
            if bouton_supprimer:
                if id_cible == "Aucun":
                    st.warning("Aucun identifiant valide sélectionné.")
                elif int(id_cible) in [1, 2]:  # Harmonisation du type en entier pour le test de sécurité
                    st.error("Action Interdite : Les identifiants 1 et 2 sont requis par le système pour les tests standard/premium.")
                else:
                    conn_del = psycopg2.connect(DB_URI)
                    cursor_del = conn_del.cursor()
                    cursor_del.execute("DELETE FROM UTILISATEUR WHERE id_client = %s;", (int(id_cible),))
                    conn_del.commit()
                    cursor_del.close()
                    conn_del.close()
                    st.success(f"Tenant ID {id_cible} supprimé avec succès !")
                    st.rerun()
    except Exception as e:
        st.caption("Initialisation du système de révocation...")
    finally:
        if conn_sidebar:
            conn_sidebar.close()

# ==========================================
# PANNEAU CENTRAL : ONGLETS PRINCIPAUX
# ==========================================
tab1, tab2, tab3 = st.tabs([" Tableaux de Bord", "👥 Gestion des Tenants (Clients)", " Pipeline Kafka & Audit"])

# --- ONGLET 1 : STATISTIQUES ET EXPORT EXCEL VERDICTS IA ENRICHI ---
with tab1:
    st.subheader("Analyse Qualification de la Menace en Temps Réel")
    try:
        conn = psycopg2.connect(DB_URI)
        
        # 1. Lecture des indicateurs clés (KPI)
        df_stats = pd.read_sql_query("""
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN verdict = TRUE THEN 1 ELSE 0 END) as fraudes,
                AVG(CAST(score_valeur AS FLOAT)) * 100 as risque_moyen
            FROM RESULTAT_STORE;
        """, conn)
        
        # 2. Jointure intelligente exclusive TFC pour lister les menaces qualifiées par le Worker
        df_verdicts = pd.read_sql_query("""
            SELECT 
                R.id_trans, 
                R.score_valeur, 
                R.verdict, 
                COALESCE(A.action, 'ANALYSE_EN_COURS') as type_menace
            FROM RESULTAT_STORE R
            LEFT JOIN AUDIT_LOGGER A ON R.id_trans = A.id_trans
            ORDER BY R.id_score DESC LIMIT 8;
        """, conn)
        
        conn.close()

        # Affichage des métriques hautes
        c1, c2, c3 = st.columns(3)
        total_val = int(df_stats['total'].iloc[0]) if not df_stats.empty and df_stats['total'].iloc[0] is not None else 0
        c1.metric("Transactions Évaluées", total_val)
        
        fraudes_raw = df_stats['fraudes'].iloc[0] if not df_stats.empty else 0
        fraudes_val = int(fraudes_raw) if fraudes_raw is not None else 0
        c2.metric("Alertes Levées (Fraudes/Suspectes)", fraudes_val)
        
        risque_raw = df_stats['risque_moyen'].iloc[0] if not df_stats.empty else 0.0
        risque_val = float(risque_raw) if risque_raw is not None else 0.0
        c3.metric("Niveau de Risque Global Moyen", f"{risque_val:.2f}%")
        
        st.markdown("### Écran de Contrôle Spécifique des Alertes Inférence IA")
        if not df_verdicts.empty:
            df_verdicts['score_valeur'] = df_verdicts['score_valeur'].apply(lambda x: float(x) if x is not None else 0.0)
            
            # Renommage explicite des colonnes pour l'administration métier
            df_verdicts.columns = ["ID Transaction", "Score Risque IA", "Statut Suspect", "Nature de la Menace Détectée"]
            
            # Affichage élégant du tableau de bord
            st.dataframe(df_verdicts, use_container_width=True, hide_index=True)
            
            # --- BOUTON DE TÉLÉCHARGEMENT EXCEL QUALIFIÉ ---
            st.markdown("###  Exporter l'historique complet qualifié")
            conn_exp = psycopg2.connect(DB_URI)
            df_export_full = pd.read_sql_query("""
                SELECT 
                    R.id_trans as "ID Transaction", 
                    R.score_valeur as "Score Risque", 
                    R.verdict as "Verdict IA",
                    A.action as "Type de Fraude Déduite",
                    A.horodatage as "Horodatage"
                FROM RESULTAT_STORE R
                LEFT JOIN AUDIT_LOGGER A ON R.id_trans = A.id_trans
                ORDER BY R.id_score DESC;
            """, conn_exp)
            conn_exp.close()

            df_export_full["Score Risque"] = df_export_full["Score Risque"].apply(lambda x: float(x) if x is not None else 0.0)

            buf1 = io.BytesIO()
            with pd.ExcelWriter(buf1, engine='openpyxl') as writer:
                df_export_full.to_excel(writer, index=False, sheet_name='Analyses_Menaces_IA')
                
            st.download_button(
                label=" Télécharger l'historique qualifié au format Excel (.xlsx)",
                data=buf1.getvalue(),
                file_name="historique_qualification_fraudes_ia.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key="btn_excel_1"
            )
        else:
            st.info("Aucun verdict enregistré pour le moment. En attente de flux Kafka...")

    except Exception as e:
        st.info("Synchronisation du flux en cours... ")

# --- ONGLET 2 : ENREGISTREMENT SECURISE ET EXPORT EXCEL PROFILS ---
with tab2:
    st.subheader("Enregistrer une nouvelle institution partenaire")
    
    if st.button(" Créer une Clé API robuste"):
        st.session_state["cle_securisee"] = f"tfc_key_{secrets.token_hex(12)}"
        st.rerun()

    with st.form("Formulaire Enregistrement Tenant", clear_on_submit=True):
        id_client_neuf = st.number_input("ID Client unique", min_value=3, step=1)
        champ_cle = st.text_input("Clé API Robuste (Obligatoire)", value=st.session_state["cle_securisee"])
        classe_qos = st.selectbox("Classe de Service QoS", ["Premium", "Standard"])
        
        soumission_enregistrement = st.form_submit_button("Valider et Activer l'accès")
        
        if soumission_enregistrement:
            if not champ_cle or champ_cle.strip() == "":
                st.error(" Enregistrement Refusé : La création d'une Clé API robuste est obligatoire.")
            else:
                try:
                    conn = psycopg2.connect(DB_URI)
                    cursor = conn.cursor()
                    cursor.execute("INSERT INTO UTILISATEUR (id_client, api_key, role) VALUES (%s, %s, %s);", (id_client_neuf, champ_cle, classe_qos))
                    conn.commit()
                    cursor.close()
                    conn.close()
                    
                    st.success(f" Le client ID {id_client_neuf} a bien été scellé dans la base PostgreSQL.")
                    st.session_state["cle_securisee"] = ""
                    st.rerun()
                except Exception as error_sql:
                    st.error(f" Erreur : Cet ID ou cette Clé existe déjà. ({error_sql})")

    st.markdown("###  Profils Clients Actifs dans PostgreSQL")
    try:
        conn = psycopg2.connect(DB_URI)
        df_visualisation = pd.read_sql_query("SELECT id_client as \"ID Client\", api_key as \"Clé API Active\", role as \"Niveau QoS / Rôle\" FROM UTILISATEUR ORDER BY id_client ASC;", conn)
        st.dataframe(df_visualisation, use_container_width=True, hide_index=True)
        
        st.markdown("###  Exporter la liste des clients actifs")
        buf2 = io.BytesIO()
        with pd.ExcelWriter(buf2, engine='openpyxl') as writer:
            df_visualisation.to_excel(writer, index=False, sheet_name='Profils_Clients')
            
        st.download_button(
            label=" Télécharger la liste des clients au format Excel (.xlsx)",
            data=buf2.getvalue(),
            file_name="liste_profils_clients.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key="btn_excel_2"
        )
        conn.close()
    except Exception as e:
        st.error(f"Erreur de lecture de la table : {e}")

# --- ONGLET 3 : LOGS AUDIT ET EXPORT EXCEL AUDIT ---
with tab3:
    st.subheader("Surveillance du Pipeline Événementiel")
    try:
        # CORRECTION RESEAU : Recherche dynamique du serveur Kafka sur le réseau Docker
        kafka_server = os.getenv("KAFKA_BROKER", "localhost:9092")
        admin = KafkaAdminClient(bootstrap_servers=[kafka_server])
        st.success("Bus Événementiel Apache Kafka : CONNECTÉ (En Ligne)")
        st.write("Canaux (Topics) détectés dans l'infrastructure :", admin.list_topics())
    except:
        st.error("Bus Événementiel Apache Kafka : CRITIQUE (Le broker Docker est inaccessible ou en cours d'initialisation)")
        
    st.markdown("### Journal d'Audit Système Global")
    try:
        conn = psycopg2.connect(DB_URI)
        df_logs = pd.read_sql_query("SELECT id_log as \"ID Log\", id_trans as \"ID Transaction\", action as \"Action / Signature Système\", niveau as \"Niveau Log\", latence_ms as \"Latence IA (ms)\", horodatage as \"Date Enregistrement\" FROM AUDIT_LOGGER ORDER BY id_log DESC LIMIT 10;", conn)
        st.dataframe(df_logs, use_container_width=True, hide_index=True)
        
        st.markdown("###  Exporter les registres d'audit système")
        df_export_logs = pd.read_sql_query("SELECT id_log as \"ID Log\", id_trans as \"ID Transaction\", action as \"Action Système\", niveau as \"Niveau\", latence_ms as \"Latence IA (ms)\", horodatage as \"Date\" FROM AUDIT_LOGGER ORDER BY id_log DESC;", conn)
        
        # Sécurisation du typage pour l'export Excel
        if not df_export_logs.empty:
            df_export_logs["Latence IA (ms)"] = df_export_logs["Latence IA (ms)"].apply(lambda x: int(x) if x is not None else 0)
        
        buf3 = io.BytesIO()
        with pd.ExcelWriter(buf3, engine='openpyxl') as writer:
            df_export_logs.to_excel(writer, index=False, sheet_name='Logs_Audit')
            
        st.download_button(
            label=" Télécharger les journaux système au format Excel (.xlsx)",
            data=buf3.getvalue(),
            file_name="journaux_audit_systeme.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key="btn_excel_3"
        )
        conn.close()
    except Exception as e:
        st.error(f"Erreur d'accès aux tables d'audit : {e}")