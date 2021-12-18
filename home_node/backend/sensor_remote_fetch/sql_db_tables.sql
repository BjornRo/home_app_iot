CREATE TABLE blocklist (
    ip VARCHAR(46) NOT NULL,
    attempts INT NOT NULL,
    total_attemps INT NOT NULL,
    first_ban_time VARCHAR(26) NOT NULL,
    banned_until VARCHAR(26) NOT NULL,
    comment TEXT NOT NULL,
    PRIMARY KEY (ip)
);