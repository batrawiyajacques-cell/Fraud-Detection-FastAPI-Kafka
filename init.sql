-- =========================================================================
-- NETTOYAGE DES ANCIENNES TABLES (Pour éviter les conflits au redémarrage)
-- =========================================================================
DROP TABLE IF EXISTS AUDIT_LOGGER CASCADE;
DROP TABLE IF EXISTS NOTIFICATION CASCADE;
DROP TABLE IF EXISTS RESULTAT_STORE CASCADE;
DROP TABLE IF EXISTS TRANSACTION CASCADE;
DROP TABLE IF EXISTS FRAUDE_DETECTOR CASCADE;
DROP TABLE IF EXISTS UTILISATEUR CASCADE;

-- =========================================================================
-- CRÉATION DES TABLES ET STRUCTURES RELATIONNELLES (Modèle Cartes de Crédit)
-- =========================================================================

-- 1. Table des Utilisateurs / Partenaires
CREATE TABLE UTILISATEUR (
    id_client INT PRIMARY KEY,
    api_key VARCHAR(64) NOT NULL UNIQUE,
    role VARCHAR(20) NOT NULL CHECK (role IN ('Client', 'Admin'))
);

-- 2. Table des Détecteurs / Modèles IA
CREATE TABLE FRAUDE_DETECTOR (
    id_detector INT PRIMARY KEY,
    model_name VARCHAR(50) NOT NULL,
    threshold FLOAT NOT NULL,
    is_trained BOOLEAN NOT NULL DEFAULT FALSE
);

-- 3. Table des Transactions
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

-- 4. Table des Résultats d'Inférence de l'IA (Optimisée pour le pipeline)
CREATE TABLE RESULTAT_STORE (
    id_score SERIAL PRIMARY KEY,
    id_trans VARCHAR(50) NOT NULL UNIQUE,
    id_detector INT NOT NULL DEFAULT 1,
    score_valeur FLOAT NOT NULL,
    verdict BOOLEAN NOT NULL,
    CONSTRAINT fk_detector_store FOREIGN KEY (id_detector) REFERENCES FRAUDE_DETECTOR(id_detector) ON DELETE RESTRICT
    -- Note TFC : La clé étrangère vers TRANSACTION est retirée ici pour permettre l'ingestion 
    -- asynchrone temps réel (Kafka -> DB) sans bloquer le Worker si l'API Gateway est plus lente.
);

-- 5. Table de Suivi des Notifications Webhooks
CREATE TABLE NOTIFICATION (
    id_notif SERIAL PRIMARY KEY,
    id_score INT NOT NULL UNIQUE,
    webhook_url VARCHAR(255) NOT NULL,
    statut_livraison VARCHAR(20) NOT NULL DEFAULT 'PENDING',
    CONSTRAINT fk_notification_score FOREIGN KEY (id_score) REFERENCES RESULTAT_STORE(id_score) ON DELETE CASCADE
);

-- 6. Table des Journaux d'Audit Système
CREATE TABLE AUDIT_LOGGER (
    id_log SERIAL PRIMARY KEY,
    id_trans VARCHAR(50) NOT NULL,
    action VARCHAR(100) NOT NULL,
    niveau VARCHAR(10) NOT NULL,
    latence_ms INT NOT NULL,
    horodatage TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- =========================================================================
-- INJECTION DES PROFILS SYSTÈMES ET DES PARAMÈTRES PAR DÉFAUT
-- =========================================================================

-- Injection de l'Administrateur de session et du Client de Test (Simulateur)
INSERT INTO UTILISATEUR (id_client, api_key, role) VALUES 
(100, 'admin_master_key_2026', 'Admin'),
(1, 'tfc_key_client_8cf90a32', 'Client')
ON CONFLICT (id_client) DO NOTHING;

-- Configuration du modèle d'inférence (Seuil calé à 0.40 pour la zone grise)
INSERT INTO FRAUDE_DETECTOR (id_detector, model_name, threshold, is_trained) VALUES 
(1, 'Random Forest Classifier (CreditCard)', 0.40, TRUE)
ON CONFLICT (id_detector) DO NOTHING;