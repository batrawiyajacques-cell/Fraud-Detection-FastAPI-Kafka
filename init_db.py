import psycopg2
import os

# Récupération dynamique des configurations (avec valeurs par défaut si exécuté en local)
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_NAME = os.getenv("DB_NAME", "tfc_db")  # Assure-toi que cela correspond au POSTGRES_DB de ton .env
DB_USER = os.getenv("DB_USER", "admin")
DB_PASS = os.getenv("DB_PASS", "MonSuperPassword2026")
DB_PORT = os.getenv("DB_PORT", "5432")

DB_URI = f"dbname={DB_NAME} user={DB_USER} password={DB_PASS} host={DB_HOST} port={DB_PORT}"

def initialiser_base_donnees():
    print(f"[TFC-DATABASE] Connexion au conteneur PostgreSQL ({DB_HOST} / {DB_NAME})...")
    try:
        conn = psycopg2.connect(DB_URI)
        cursor = conn.cursor()
        
        print("[TFC-DATABASE] Nettoyage des anciennes tables...")
        cursor.execute("""
            DROP TABLE IF EXISTS AUDIT_LOGGER CASCADE;
            DROP TABLE IF EXISTS NOTIFICATION CASCADE;
            DROP TABLE IF EXISTS RESULTAT_STORE CASCADE;
            DROP TABLE IF EXISTS TRANSACTION CASCADE;
            DROP TABLE IF EXISTS FRAUDE_DETECTOR CASCADE;
            DROP TABLE IF EXISTS UTILISATEUR CASCADE;
        """)
        
        print("[TFC-DATABASE] Creation des nouvelles tables (Modele Cartes de Credit)...")
        sql_script = """
        CREATE TABLE UTILISATEUR (
            id_client INT PRIMARY KEY,
            api_key VARCHAR(64) NOT NULL UNIQUE,
            role VARCHAR(20) NOT NULL CHECK (role IN ('Client', 'Admin'))
        );

        CREATE TABLE FRAUDE_DETECTOR (
            id_detector INT PRIMARY KEY,
            model_name VARCHAR(50) NOT NULL,
            threshold FLOAT NOT NULL,
            is_trained BOOLEAN NOT NULL DEFAULT FALSE
        );

        CREATE TABLE TRANSACTION (
            id_trans VARCHAR(50) PRIMARY KEY,
            id_client INT NOT NULL,
            tx_time FLOAT NOT NULL,
            amount DECIMAL(15,2) NOT NULL,
            v1 FLOAT, v2 FLOAT, v3 FLOAT, v4 FLOAT, v5 FLOAT,
            v6 FLOAT, v7 FLOAT, v8 FLOAT, v9 FLOAT, v10 FLOAT,
            v11 FLOAT, v12 FLOAT, v13 FLOAT, v14 FLOAT, v15 FLOAT,
            v16 FLOAT, v17 FLOAT, v18 FLOAT, v19 FLOAT, v20 FLOAT,
            v21 FLOAT, v22 FLOAT, v23 FLOAT, v24 FLOAT, v25 FLOAT,
            v26 FLOAT, v27 FLOAT, v28 FLOAT,
            processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT fk_transaction_utilisateur FOREIGN KEY (id_client) REFERENCES UTILISATEUR(id_client) ON DELETE RESTRICT
        );

        CREATE TABLE RESULTAT_STORE (
            id_score SERIAL PRIMARY KEY,
            id_trans VARCHAR(50) NOT NULL UNIQUE,
            id_detector INT NOT NULL,
            score_valeur FLOAT NOT NULL,
            verdict BOOLEAN NOT NULL,
            CONSTRAINT fk_store_transaction FOREIGN KEY (id_trans) REFERENCES TRANSACTION(id_trans) ON DELETE CASCADE,
            CONSTRAINT fk_detector_store FOREIGN KEY (id_detector) REFERENCES FRAUDE_DETECTOR(id_detector) ON DELETE RESTRICT
        );

        CREATE TABLE NOTIFICATION (
            id_notif SERIAL PRIMARY KEY,
            id_score INT NOT NULL UNIQUE,
            webhook_url VARCHAR(255) NOT NULL,
            statut_livraison VARCHAR(20) NOT NULL DEFAULT 'PENDING',
            CONSTRAINT fk_notification_score FOREIGN KEY (id_score) REFERENCES RESULTAT_STORE(id_score) ON DELETE CASCADE
        );

        CREATE TABLE AUDIT_LOGGER (
            id_log SERIAL PRIMARY KEY,
            id_trans VARCHAR(50) NOT NULL,
            action VARCHAR(100) NOT NULL,
            niveau VARCHAR(10) NOT NULL,
            latence_ms INT NOT NULL,
            horodatage TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT fk_audit_transaction FOREIGN KEY (id_trans) REFERENCES TRANSACTION(id_trans) ON DELETE CASCADE
        );

        -- Injection des profils systemes et de l'ADMINISTRATEUR
        INSERT INTO UTILISATEUR (id_client, api_key, role) VALUES 
        (100, 'admin_master_key_2026', 'Admin'),
        (1, 'tfc_key_client_8cf90a32', 'Client') ON CONFLICT DO NOTHING;

        -- Seuil standard a 0.40 pour correspondre au declenchement de la Zone Grise du Worker
        INSERT INTO FRAUDE_DETECTOR (id_detector, model_name, threshold, is_trained) VALUES 
        (1, 'Random Forest Classifier (CreditCard)', 0.40, TRUE) ON CONFLICT DO NOTHING;
        """
        
        cursor.execute(sql_script)
        conn.commit()
        print(f"[TFC-DATABASE] Succes ! Les tables ont ete initialisees dans '{DB_NAME}'.")
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"[ERREUR] Echec de l'initialisation SQL : {e}")

if __name__ == "__main__":
    initialiser_base_donnees()