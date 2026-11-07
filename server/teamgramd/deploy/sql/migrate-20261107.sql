UPDATE users
SET first_name = 'Chat',
    username = CASE WHEN username = 'teamgram' THEN '' ELSE username END
WHERE id = 777000
  AND first_name = 'Teamgram';
