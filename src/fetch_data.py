import io
import sys

import chess.pgn
import requests
import zstandard as zstd

# URL of a Lichess dump (using a smaller month for testing/demo purposes)
# You can find the list here: https://database.lichess.org/
URL = "https://database.lichess.org/standard/lichess_db_standard_rated_2017-01.pgn.zst"


def fetch_games(url, max_games=10):
    print(f"Connecting to {url}...")
    # Stream the response
    response = requests.get(url, stream=True)
    response.raise_for_status()

    # Create a streaming decompressor
    dctx = zstd.ZstdDecompressor()

    # Wrap the response stream in a decompressor stream
    # We use a large read size to be efficient
    reader = dctx.stream_reader(response.raw)

    # Wrap in a text stream for python-chess
    text_reader = io.TextIOWrapper(reader, encoding="utf-8")

    print("Streaming and parsing games...")
    count = 0
    matched = 0

    while matched < max_games:
        game = chess.pgn.read_game(text_reader)
        if game is None:
            break

        count += 1

        # Extract headers
        headers = game.headers
        white_elo = headers.get("WhiteElo", "?")
        black_elo = headers.get("BlackElo", "?")
        time_control = headers.get("TimeControl", "?")

        # Simple filter: Amateurs (Elo < 1500) in Blitz (e.g., 180+0 or 300+0)
        try:
            w_elo = int(white_elo)
            b_elo = int(black_elo)

            if w_elo < 1500 and b_elo < 1500:
                # Check if game has analysis (look for %eval in comments)
                has_analysis = False
                node = game
                # Check the first 20 moves for analysis to be sure
                for _ in range(20):
                    node = node.next()
                    if node is None:
                        break
                    if node.comment and "%eval" in node.comment:
                        has_analysis = True
                        break

                if has_analysis:
                    print(game)
                    print(
                        f"Game #{count}: {headers.get('White')} ({w_elo}) vs {headers.get('Black')} ({b_elo}) [{time_control}]"
                    )
                    print(f"Sample move comment: {node.comment}")
                    matched += 1

        except ValueError:
            continue

        if count % 1000 == 0:
            print(f"Scanned {count} games...")

    print(f"Done. Found {matched} matching games out of {count} scanned.")


if __name__ == "__main__":
    fetch_games(URL)
