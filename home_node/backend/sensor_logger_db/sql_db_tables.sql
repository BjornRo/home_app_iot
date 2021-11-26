CREATE TABLE locations (name VARCHAR(10) PRIMARY KEY);

CREATE TABLE devices (name VARCHAR(10) PRIMARY KEY);

CREATE TABLE measureTypes (name VARCHAR(16) PRIMARY KEY);

CREATE TABLE timestamps (time VARCHAR(16) NOT NULL PRIMARY KEY);

CREATE TABLE measurements (
    location VARCHAR(10) NOT NULL UNIQUE,
    device VARCHAR(10) NOT NULL,
    mtype VARCHAR(10) NOT NULL,
    time VARCHAR(16) NOT NULL,
    value NUMERIC(2) NOT NULL,
    PRIMARY KEY (location, device, mtype, time),
    FOREIGN KEY (location) REFERENCES Locations (name),
    FOREIGN KEY (device) REFERENCES Devices (name),
    FOREIGN KEY (mtype) REFERENCES MeasureTypes (name),
    FOREIGN KEY (time) REFERENCES Timestamps (time)
);
