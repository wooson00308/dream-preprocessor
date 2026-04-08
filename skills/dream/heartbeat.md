## dream-{slug_short}
- slug: {slug}
- prompt: /dream
- interval: 3h
- timeout: 10m
- condition: dream-prep status --slug="{slug}" | grep -q "미처리: 0" && exit 1 || exit 0
- notify: all
