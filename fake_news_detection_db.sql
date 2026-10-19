-- =====================================================================
-- Fake News Detection System - MySQL schema (Safe / Non-Destructive)
-- Requires MySQL 8.0.16+ (CHECK constraints are enforced from this version)
-- =====================================================================

-- NOTE: Destructive DROP DATABASE is intentionally omitted to protect existing data.
-- To reset a local development database manually, drop it explicitly before running.
CREATE DATABASE IF NOT EXISTS fake_news_detection_db
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

USE fake_news_detection_db;

-- ---------------------------------------------------------------------
-- USER
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `user` (
    user_id       INT UNSIGNED  NOT NULL AUTO_INCREMENT,
    name          VARCHAR(100)  NOT NULL,
    email         VARCHAR(255)  NOT NULL,
    password      VARCHAR(255)  NOT NULL COMMENT 'Password HASH only, never plaintext',
    role          ENUM('user','moderator') NOT NULL DEFAULT 'user',
    created_at    DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_user PRIMARY KEY (user_id),
    CONSTRAINT uq_user_email UNIQUE (email)
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- ADMIN
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `admin` (
    admin_id      INT UNSIGNED  NOT NULL AUTO_INCREMENT,
    name          VARCHAR(100)  NOT NULL,
    email         VARCHAR(255)  NOT NULL,
    password      VARCHAR(255)  NOT NULL COMMENT 'Password HASH only, never plaintext',
    CONSTRAINT pk_admin PRIMARY KEY (admin_id),
    CONSTRAINT uq_admin_email UNIQUE (email)
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- NEWS  (USER 1 : N NEWS)
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `news` (
    news_id       INT UNSIGNED  NOT NULL AUTO_INCREMENT,
    user_id       INT UNSIGNED  NOT NULL,
    headline      VARCHAR(500)  NOT NULL,
    article_text  MEDIUMTEXT    NOT NULL,
    submitted_at  DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_news PRIMARY KEY (news_id),
    CONSTRAINT fk_news_user FOREIGN KEY (user_id)
        REFERENCES `user` (user_id)
        ON DELETE CASCADE
        ON UPDATE CASCADE,
    INDEX idx_news_user_id (user_id),
    INDEX idx_news_submitted_at (submitted_at),
    INDEX idx_news_headline (headline(191))
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- PREDICTION  (NEWS 1 : N PREDICTION)
-- confidence_score: 0.0000 - 1.0000 (e.g. Logistic Regression probability)
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `prediction` (
    prediction_id    INT UNSIGNED  NOT NULL AUTO_INCREMENT,
    news_id          INT UNSIGNED  NOT NULL,
    result           ENUM('Real','Fake') NOT NULL,
    confidence_score DECIMAL(5,4)  NOT NULL,
    predicted_at     DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_prediction PRIMARY KEY (prediction_id),
    CONSTRAINT fk_prediction_news FOREIGN KEY (news_id)
        REFERENCES `news` (news_id)
        ON DELETE CASCADE
        ON UPDATE CASCADE,
    CONSTRAINT chk_prediction_result CHECK (result IN ('Real','Fake')),
    CONSTRAINT chk_prediction_confidence CHECK (confidence_score BETWEEN 0 AND 1),
    INDEX idx_prediction_news_id (news_id),
    INDEX idx_prediction_result (result),
    INDEX idx_prediction_predicted_at (predicted_at)
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- DATASET  (ADMIN 1 : N DATASET)
-- admin_id is nullable so records survive if an admin is removed.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `dataset` (
    dataset_id    INT UNSIGNED  NOT NULL AUTO_INCREMENT,
    admin_id      INT UNSIGNED  NULL,
    news_text     MEDIUMTEXT    NOT NULL,
    label         ENUM('Real','Fake') NOT NULL,
    added_at      DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_dataset PRIMARY KEY (dataset_id),
    CONSTRAINT fk_dataset_admin FOREIGN KEY (admin_id)
        REFERENCES `admin` (admin_id)
        ON DELETE SET NULL
        ON UPDATE CASCADE,
    CONSTRAINT chk_dataset_label CHECK (label IN ('Real','Fake')),
    INDEX idx_dataset_admin_id (admin_id),
    INDEX idx_dataset_label (label),
    INDEX idx_dataset_added_at (added_at)
) ENGINE=InnoDB;

-- =====================================================================
-- OPTIONAL: example of inserting dataset records later.
-- SAMPLE DATA ONLY - NOT part of your real dataset. Uncomment to try.
-- =====================================================================
-- INSERT INTO `dataset` (admin_id, news_text, label) VALUES
--     (NULL, 'SAMPLE: Government announces new public transport schedule.', 'Real'),
--     (NULL, 'SAMPLE: Miracle fruit cures every disease overnight, doctors stunned.', 'Fake');
