from src.tilt_checks import (
    analyze_tilt_move,
    did_opponent_cancel_blunder,
    is_already_lost,
    is_in_time_trouble,
    is_significant_eval_drop,
    is_still_winning,
    is_traumatic_blunder,
)

from .parser import parse_comment


def analyze_game_for_tilt(game, player_color):
    """
    Analyzes a game to find tilt moments for a specific player (White or Black).

    Tilt Definition (Speed Tilt):
    1. Blunder: Eval drops by > 200 cp (from player's perspective).
    2. Tilt Sequence: Next 2-3 moves played fast (< 5s) AND are suboptimal.
    Analyzes a game for "tilt" moments for a specific player (True=White, False=Black).
    Returns a list of tilt events.
    """
    tilt_events = []

    # We need to track move times to calculate average speed
    white_move_times = []
    black_move_times = []

    node = game
    prev_eval = 0  # Start at 0 cp
    is_white_turn = True  # White starts

    while node and node.next():
        next_node = node.next()

        # Parse comment for eval and clock
        if next_node.comment:
            data = parse_comment(next_node.comment)
            current_eval = data.get("eval")
            clk = data.get("clk")

            # Calculate move number (ply / 2 + 1)
            move_num = (next_node.ply() + 1) // 2

            # Calculate time spent for this move
            time_spent = None
            if node.parent:  # We need previous move's clock
                prev_data = parse_comment(node.comment)
                prev_clk = prev_data.get("clk")
                if clk is not None and prev_clk is not None:
                    time_spent = prev_clk - clk

            # Update speed stats (ONLY for moves >= 12)
            if time_spent is not None and move_num >= 12:
                if is_white_turn:
                    white_move_times.append(time_spent)
                else:
                    black_move_times.append(time_spent)

            if current_eval is not None:
                # Calculate diff from player's perspective
                diff = 0
                if is_white_turn:
                    diff = current_eval - prev_eval
                else:
                    diff = prev_eval - current_eval

                # Check for Blunder (ONLY for moves >= 12)
                # We use is_traumatic_blunder which handles context (already lost, still winning, etc.)
                if (move_num >= 12) and (is_white_turn == player_color):
                    # Convert evals to player's perspective
                    p_prev_eval = prev_eval if is_white_turn else -prev_eval
                    p_curr_eval = current_eval if is_white_turn else -current_eval

                    if is_traumatic_blunder(p_prev_eval, p_curr_eval):
                        # 0. Ignore if in time trouble (< 10s)
                        if is_in_time_trouble(clk, 10):
                            prev_eval = current_eval
                            node = next_node
                            is_white_turn = not is_white_turn
                            continue

                        # 1. Check if opponent cancelled blunder
                        opponent_node = next_node.next()
                        if did_opponent_cancel_blunder(
                            opponent_node, current_eval, is_white_turn
                        ):
                            # Skip this blunder
                            prev_eval = current_eval
                            node = next_node
                            is_white_turn = not is_white_turn
                            continue

                        # Calculate average time for this player so far
                        player_times = (
                            white_move_times if is_white_turn else black_move_times
                        )
                        avg_time = (
                            sum(player_times) / len(player_times)
                            if player_times
                            else 10.0
                        )

                        # Threshold: 50% of average speed
                        speed_threshold = avg_time * 0.5

                        # BLUNDER DETECTED! Check next moves for tilt sequence.
                        tilt_sequence = []
                        temp_node = next_node

                        for _ in range(3):
                            # Opponent move
                            temp_node = temp_node.next()
                            if temp_node is None:
                                break

                            # Player move (Potential Tilt Move)
                            temp_node = temp_node.next()
                            if temp_node is None:
                                break

                            # Analyze tilt move using helper
                            tilt_move_data = analyze_tilt_move(
                                temp_node, speed_threshold, is_white_turn
                            )

                            if tilt_move_data:
                                tilt_sequence.append(tilt_move_data)
                            else:
                                break

                        # If we found at least 2 fast moves, check if at least one was bad
                        # The user wants to be sure it's a "craquage" (meltdown).
                        # So we require at least one move in the sequence to drop eval by > 100 cp (1 pawn).
                        if len(tilt_sequence) >= 2:
                            has_significant_drop = any(
                                m["eval_diff"] < -100 for m in tilt_sequence
                            )

                            if has_significant_drop:
                                # Final Check: Did the evaluation drop persist at the end of the sequence?
                                # We compare the eval at the end of the sequence (current_eval)
                                # with the eval BEFORE the blunder (prev_eval).
                                # The net drop must be significant (e.g. > 200 cp).

                                # We need to get the eval at the end of the sequence.
                                # next_node is currently pointing to the last move of the sequence (temp_node).
                                # We need to parse it if we haven't already.
                                seq_end_eval = None
                                if temp_node and temp_node.comment:
                                    seq_end_data = parse_comment(temp_node.comment)
                                    seq_end_eval = seq_end_data.get("eval")

                                if seq_end_eval is not None:
                                    seq_diff = 0
                                    if is_white_turn:  # White tilted
                                        seq_diff = seq_end_eval - prev_eval
                                    else:  # Black tilted
                                        seq_diff = prev_eval - seq_end_eval

                                    # If the net drop is significant (> 300 cp), confirm tilt.
                                    if seq_diff < -300:
                                        blunder_num = (next_node.ply() + 1) // 2
                                        tilt_events.append(
                                            {
                                                "blunder_move": next_node.san(),
                                                "blunder_number": blunder_num,
                                                "blunder_eval_drop": diff,
                                                "tilt_sequence": tilt_sequence,
                                                "avg_time_before_blunder": round(
                                                    avg_time, 2
                                                ),
                                            }
                                        )

                                # Fast-forward to avoid overlapping tilts
                                next_node = temp_node
                                if next_node and next_node.comment:
                                    end_data = parse_comment(next_node.comment)
                                    if end_data.get("eval") is not None:
                                        current_eval = end_data.get("eval")

                prev_eval = current_eval

        node = next_node
        is_white_turn = not is_white_turn

    return tilt_events
