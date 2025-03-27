-- Table: email_accounts
CREATE TABLE email_accounts (
    id bigint PRIMARY KEY NOT NULL,
    created_at timestamp with time zone DEFAULT now(),
    user_id uuid NOT NULL,
    imap_port smallint,
    disconnected boolean DEFAULT false,
    last_error text,
    imap_server text,
    email character varying UNIQUE,
    email_provider character varying,
    pwd text,
    imap_login character varying,
    imap_pwd character varying
);


-- Table: outlook_states
CREATE TABLE outlook_states (
    id bigint PRIMARY KEY NOT NULL,
    created_at timestamp with time zone DEFAULT now(),
    state text,
    user_id text
);


-- Table: received_emails
CREATE TABLE received_emails (
    id bigint PRIMARY KEY NOT NULL,
    created_at timestamp with time zone DEFAULT now(),
    draft_created boolean DEFAULT false,
    email_classified boolean DEFAULT false,
    sender character varying,
    smtp_msg_id text,
    email_account character varying
);
