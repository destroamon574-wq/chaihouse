-- Схема БД «ЧайHouse», версия 2.
-- SQL совместим с PostgreSQL с точностью до типов и AUTOINCREMENT.

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS schema_migrations (
    version     INTEGER PRIMARY KEY,
    applied_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS users (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT NOT NULL CHECK(length(name) BETWEEN 2 AND 80),
    email           TEXT NOT NULL UNIQUE COLLATE NOCASE,
    phone           TEXT,
    password_hash   TEXT NOT NULL,
    role            TEXT NOT NULL DEFAULT 'guest' CHECK(role IN ('guest', 'admin', 'owner')),
    session_version INTEGER NOT NULL DEFAULT 1,
    is_active       INTEGER NOT NULL DEFAULT 1,
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_users_role ON users(role);

CREATE TABLE IF NOT EXISTS password_resets (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash  TEXT NOT NULL UNIQUE,
    expires_at  TEXT NOT NULL,
    used_at     TEXT,
    created_at  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_password_resets_user ON password_resets(user_id);

CREATE TABLE IF NOT EXISTS halls (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    slug        TEXT NOT NULL UNIQUE,
    name        TEXT NOT NULL,
    tagline     TEXT,
    description TEXT NOT NULL,
    capacity    INTEGER NOT NULL CHECK(capacity > 0),
    min_spend   INTEGER NOT NULL DEFAULT 0 CHECK(min_spend >= 0),
    image       TEXT NOT NULL,
    features    TEXT NOT NULL DEFAULT '[]',
    sort_order  INTEGER NOT NULL DEFAULT 0,
    is_active   INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS dining_tables (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    hall_id   INTEGER NOT NULL REFERENCES halls(id) ON DELETE CASCADE,
    name      TEXT NOT NULL,
    seats     INTEGER NOT NULL CHECK(seats BETWEEN 1 AND 30),
    is_active INTEGER NOT NULL DEFAULT 1,
    UNIQUE(hall_id, name)
);
CREATE INDEX IF NOT EXISTS idx_tables_hall ON dining_tables(hall_id);

CREATE TABLE IF NOT EXISTS menu_categories (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    slug        TEXT NOT NULL UNIQUE,
    name        TEXT NOT NULL,
    description TEXT,
    sort_order  INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS dishes (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    category_id       INTEGER NOT NULL REFERENCES menu_categories(id) ON DELETE RESTRICT,
    slug              TEXT NOT NULL UNIQUE,
    name              TEXT NOT NULL,
    short_description TEXT NOT NULL,
    description       TEXT NOT NULL,
    price             INTEGER NOT NULL CHECK(price >= 0),
    weight            TEXT,
    calories          INTEGER CHECK(calories IS NULL OR calories >= 0),
    allergens         TEXT,
    image             TEXT NOT NULL,
    is_vegetarian     INTEGER NOT NULL DEFAULT 0,
    is_spicy          INTEGER NOT NULL DEFAULT 0,
    is_signature      INTEGER NOT NULL DEFAULT 0,
    is_active         INTEGER NOT NULL DEFAULT 1,
    sort_order        INTEGER NOT NULL DEFAULT 0,
    created_at        TEXT NOT NULL,
    updated_at        TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_dishes_category ON dishes(category_id);
CREATE INDEX IF NOT EXISTS idx_dishes_active ON dishes(is_active);

CREATE TABLE IF NOT EXISTS bookings (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    code          TEXT NOT NULL UNIQUE,
    user_id       INTEGER REFERENCES users(id) ON DELETE SET NULL,
    hall_id       INTEGER NOT NULL REFERENCES halls(id) ON DELETE RESTRICT,
    table_id      INTEGER NOT NULL REFERENCES dining_tables(id) ON DELETE RESTRICT,
    guest_name    TEXT NOT NULL,
    guest_phone   TEXT NOT NULL,
    guest_email   TEXT,
    date          TEXT NOT NULL,
    time          TEXT NOT NULL,
    start_min     INTEGER NOT NULL CHECK(start_min >= 0 AND start_min < 1440),
    end_min       INTEGER NOT NULL CHECK(end_min > start_min),
    guests_count  INTEGER NOT NULL CHECK(guests_count BETWEEN 1 AND 30),
    occasion      TEXT,
    comment       TEXT,
    status        TEXT NOT NULL DEFAULT 'pending'
                  CHECK(status IN ('pending', 'confirmed', 'cancelled', 'declined', 'completed')),
    cancel_reason TEXT,
    created_at    TEXT NOT NULL,
    updated_at    TEXT NOT NULL,
    confirmed_by  INTEGER REFERENCES users(id) ON DELETE SET NULL,
    cancelled_by  INTEGER REFERENCES users(id) ON DELETE SET NULL,
    reminded_at   TEXT
);
CREATE INDEX IF NOT EXISTS idx_bookings_date ON bookings(date, status);
CREATE INDEX IF NOT EXISTS idx_bookings_user ON bookings(user_id);
CREATE INDEX IF NOT EXISTS idx_bookings_table ON bookings(table_id, date);
CREATE UNIQUE INDEX IF NOT EXISTS uq_bookings_active_slot
    ON bookings(table_id, date, start_min)
    WHERE status IN ('pending', 'confirmed');

CREATE TABLE IF NOT EXISTS reviews (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id      INTEGER REFERENCES users(id) ON DELETE SET NULL,
    booking_id   INTEGER REFERENCES bookings(id) ON DELETE SET NULL,
    author_name  TEXT NOT NULL,
    rating       INTEGER NOT NULL CHECK(rating BETWEEN 1 AND 5),
    text         TEXT NOT NULL CHECK(length(text) BETWEEN 10 AND 1200),
    status       TEXT NOT NULL DEFAULT 'pending'
                 CHECK(status IN ('pending', 'published', 'rejected')),
    admin_reply  TEXT,
    created_at   TEXT NOT NULL,
    moderated_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
    moderated_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_reviews_status ON reviews(status, created_at);

CREATE TABLE IF NOT EXISTS favorites (
    user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    dish_id    INTEGER NOT NULL REFERENCES dishes(id) ON DELETE CASCADE,
    created_at TEXT NOT NULL,
    PRIMARY KEY (user_id, dish_id)
);

CREATE TABLE IF NOT EXISTS notifications (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title      TEXT NOT NULL,
    body       TEXT NOT NULL,
    link       TEXT,
    is_read    INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_notifications_user ON notifications(user_id, is_read);

CREATE TABLE IF NOT EXISTS gallery_images (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    title      TEXT NOT NULL,
    alt        TEXT NOT NULL,
    image      TEXT NOT NULL,
    category   TEXT NOT NULL DEFAULT 'interior'
               CHECK(category IN ('interior', 'food', 'details')),
    sort_order INTEGER NOT NULL DEFAULT 0,
    is_active  INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS audit_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    actor_id    INTEGER REFERENCES users(id) ON DELETE SET NULL,
    action      TEXT NOT NULL,
    entity_type TEXT,
    entity_id   TEXT,
    meta        TEXT,
    ip          TEXT,
    created_at  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_audit_created ON audit_log(created_at);
