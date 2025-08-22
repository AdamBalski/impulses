#!/usr/bin/env bash

echo -n "Enter new token: "
read -s TOKEN
echo

# hash locally
HASHED=$(python3 - <<EOF
import bcrypt, os
hashed = bcrypt.hashpw(b"$TOKEN", bcrypt.gensalt())
print(hashed.decode("utf-8"))
EOF
)

# write env file on remote
ssh "$REMOTE_HOST" bash <<EOF
    echo "Updating token..."
    echo -n $HASHED > ~/.hashed_impulses_token
    echo "Token updated at \$(date)"
EOF

echo "Token rotated on $REMOTE_HOST"

