CREATE TABLE locations (name VARCHAR(10) PRIMARY KEY);

CREATE TABLE devices (name VARCHAR(10) PRIMARY KEY);

CREATE TABLE measureTypes (name VARCHAR(16) PRIMARY KEY);

CREATE TABLE deviceMeasures (
    name VARCHAR(16),
    mtype VARCHAR(16),
    PRIMARY KEY (name, mtype),
    FOREIGN KEY (name) REFERENCES devices (name),
    FOREIGN KEY (mtype) REFERENCES measureTypes (name)
);

CREATE TABLE timestamps (time VARCHAR(16) NOT NULL PRIMARY KEY);

CREATE TABLE measurements (
    location VARCHAR(10) NOT NULL UNIQUE,
    device VARCHAR(10) NOT NULL,
    mtype VARCHAR(10) NOT NULL,
    time VARCHAR(16) NOT NULL,
    value NUMERIC(2) NOT NULL,
    PRIMARY KEY (location, device, mtype, time),
    FOREIGN KEY (location) REFERENCES locations (name),
    FOREIGN KEY (device) REFERENCES devices (name),
    FOREIGN KEY (mtype) REFERENCES measureTypes (name),
    FOREIGN KEY (time) REFERENCES timestamps (time)
);