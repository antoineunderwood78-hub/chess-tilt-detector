from src.tilt import analyze_game_for_tilt
import chess.pgn
import io
import sys
import requests
import zstandard as zstd

# URL of a Lichess dump (using a smaller month for testing/demo purposes)
# You can find the list here: https://database.lichess.org/
URL = "https://database.lichess.org/standard/lichess_db_standard_rated_2025-11.pgn.zst"

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
    analyzed_count = 0
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

        def is_blitz(tc):
            # Format: "180+2" or "300+0"
            try:
                base = int(tc.split('+')[0])
                # Blitz: 180s (3min) <= base <= 300s (5min)
                return 180 <= base <= 300
            except:
                return False

        try:
            w_elo = int(white_elo)
            b_elo = int(black_elo)
            
            if w_elo < 1500 and b_elo < 1500 and is_blitz(time_control):
                # Check if game has analysis (evals AND clock)
                # We look at the first few moves to see if there are comments with %eval and %clk
                has_analysis = False
                node = game
                for _ in range(20):
                    node = node.next()
                    if node is None: break
                    if node.comment and "%eval" in node.comment and "%clk" in node.comment:
                        has_analysis = True
                        break
                
                if not has_analysis:
                    continue

                analyzed_count += 1
                # print(f"Checking game {count}...")
                # Analyze for White Tilt
                white_tilts = analyze_game_for_tilt(game, True) # True for White
                # Analyze for Black Tilt
                black_tilts = analyze_game_for_tilt(game, False) # False for Black
                
                if white_tilts or black_tilts:
                    print(f"\nGame #{count}: {headers.get('White')} ({w_elo}) vs {headers.get('Black')} ({b_elo}) [{time_control}]")
                    print(f"lien partie : {headers.get('Site')}")
                    
                    for t in white_tilts:
                        print(f"  WHITE TILT! Blunder: {t['blunder_number']}. {t['blunder_move']} (Eval drop: {t['blunder_eval_drop']})")
                        print(f"    -> Followed by: {[str(m['move_number']) + '. ' + m['move_san'] + ' (' + str(m['time_spent']) + 's)' for m in t['tilt_sequence']]}")
                        
                    for t in black_tilts:
                        print(f"  BLACK TILT! Blunder: {t['blunder_number']}. {t['blunder_move']} (Eval drop: {t['blunder_eval_drop']})")
                        print(f"    -> Followed by: {[str(m['move_number']) + '. ' + m['move_san'] + ' (' + str(m['time_spent']) + 's)' for m in t['tilt_sequence']]}")

                    matched += 1
                
        except ValueError:
            continue
            
        if count % 1000 == 0:
            print(f"Scanned {count} games (Analyzed: {analyzed_count})...")

    if analyzed_count > 0:
        percentage = (matched / analyzed_count) * 100
        print(f"Done. Found {matched} matching games out of {analyzed_count} analyzed games ({percentage:.2f}%).")
        print(f"Total games scanned in file: {count}")
    else:
        print(f"Done. No games met the criteria for analysis out of {count} scanned.")

if __name__ == "__main__":
    fetch_games(URL)
