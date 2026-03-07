#!/bin/bash

BRANCH="claude/navigate-bininga-folder-dQXWr"
FILE="BININGA_v5.html"
LAST_HASH=""

echo "👁️  Surveillance de $FILE — push auto sur $BRANCH"

while true; do
  CURRENT_HASH=$(md5sum "$FILE" 2>/dev/null | cut -d' ' -f1)

  if [ "$CURRENT_HASH" != "$LAST_HASH" ] && [ -n "$LAST_HASH" ]; then
    echo "🔄 Modification détectée — commit + push..."
    git add "$FILE"
    git commit -m "MAJ automatique BININGA_v5.html"
    git push -u origin "$BRANCH"
    echo "✅ Push effectué"
  fi

  LAST_HASH="$CURRENT_HASH"
  sleep 3
done
