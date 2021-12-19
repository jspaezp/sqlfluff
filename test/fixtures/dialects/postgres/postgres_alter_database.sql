ALTER DATABASE db;
ALTER DATABASE db ALLOW_CONNECTIONS true;
ALTER DATABASE db WITH ALLOW_CONNECTIONS true;
ALTER DATABASE db CONNECTION LIMIT 10;
ALTER DATABASE db WITH CONNECTION LIMIT 10;
ALTER DATABASE db IS_TEMPLATE true;
ALTER DATABASE db WITH IS_TEMPLATE true;
ALTER DATABASE db IS_TEMPLATE true ALLOW_CONNECTIONS true;
ALTER DATABASE db WITH IS_TEMPLATE true ALLOW_CONNECTIONS true;
ALTER DATABASE db CONNECTION LIMIT 10 IS_TEMPLATE true ALLOW_CONNECTIONS true;
ALTER DATABASE db WITH CONNECTION LIMIT 10 IS_TEMPLATE true ALLOW_CONNECTIONS true;

ALTER DATABASE db RENAME TO new_db;
ALTER DATABASE db OWNER TO other_role;
ALTER DATABASE db OWNER TO CURRENT_ROLE;
ALTER DATABASE db OWNER TO CURRENT_USER;
ALTER DATABASE db OWNER TO SESSION_USER;

-- Issue:2017
ALTER DATABASE postgres SET password_encryption TO 'scram-sha-256';
ALTER DATABASE db SET TABLESPACE new_tablespace;
ALTER DATABASE db SET parameter1 TO 1;
ALTER DATABASE db SET parameter1 TO 'some_value';
ALTER DATABASE db SET parameter1 TO DEFAULT;
ALTER DATABASE db SET parameter1 = 1;
ALTER DATABASE db SET parameter1 = 'some_value';
ALTER DATABASE db SET parameter1 = DEFAULT;
ALTER DATABASE db SET parameter1 FROM CURRENT;

ALTER DATABASE db RESET parameter1;
ALTER DATABASE db RESET ALL;