from src.parser import parse_comment


def is_traumatic_blunder(prev_eval, curr_eval):
    """
    Determines if a blunder is psychologically painful ("traumatic").
    Evals are in centipawns from the player's perspective.
    """

    # 1. Raw loss calculation (Must be a blunder > 200cp)
    loss = prev_eval - curr_eval
    if loss < 200:
        return False

    # 2. "Blasé" filter (If already significantly lost)
    # If I had -3.00 and go to -5.00, I don't care, I was already lost.
    if prev_eval < -300:
        return False

    # 3. "Luxury" filter (If still significantly winning)
    # If I had +10.00 and go to +7.00, I don't care, I'm still winning.
    if curr_eval > 400:
        return False

    # 4. If passed, the blunder changed the game's destiny
    return True


def is_significant_eval_drop(diff, threshold=-300):
    """
    Checks if the evaluation drop is significant enough to be a blunder.
    DEPRECATED: Use is_traumatic_blunder instead.
    """
    return diff < threshold


def is_already_lost(eval_val, is_white_turn, threshold=500):
    """
    Checks if the player was already in a lost position before the move.
    DEPRECATED: Use is_traumatic_blunder instead.
    """
    if is_white_turn:
        return eval_val < -threshold
    else:
        return eval_val > threshold


def is_still_winning(eval_val, is_white_turn, threshold=500):
    """
    Checks if the player is still winning after the move despite the blunder.
    DEPRECATED: Use is_traumatic_blunder instead.
    """
    if is_white_turn:
        return eval_val > threshold
    else:
        return eval_val < -threshold


def did_opponent_cancel_blunder(
    opponent_node, current_eval, is_white_turn, threshold=200
):
    """
    Checks if the opponent immediately blundered back, restoring the evaluation.
    """
    if not opponent_node:
        return False

    op_comment = parse_comment(opponent_node.comment)
    op_eval = op_comment.get("eval")

    if op_eval is None:
        return False

    op_diff = 0
    if is_white_turn:
        # White blundered, now it's Black's turn.
        # We check if eval swings back to White (positive change).
        op_diff = op_eval - current_eval
    else:
        # Black blundered, now it's White's turn.
        # We check if eval swings back to Black (negative change from White's perspective,
        # but here we want to see if it cancels the previous swing).
        # Wait, let's keep it simple:
        # White blunder: Eval dropped (e.g. +100 -> -200).
        # Opponent (Black) blunder back: Eval rises (e.g. -200 -> +100).
        # So op_diff = op_eval - current_eval should be > 200.

        # Black blunder: Eval rose (e.g. -100 -> +200).
        # Opponent (White) blunder back: Eval drops (e.g. +200 -> -100).
        # So op_diff = current_eval - op_eval should be > 200.
        op_diff = current_eval - op_eval

    return op_diff > threshold


def is_in_time_trouble(clk, threshold=30):
    """
    Checks if the player is in time trouble (low clock).
    clk is in seconds.
    """
    if clk is None:
        return False
    return clk < threshold


def analyze_tilt_move(node, speed_threshold, is_white_turn):
    """
    Analyzes a single move in the potential tilt sequence.
    Returns a dict with details if it's a valid tilt move, None otherwise.
    """
    t_data = parse_comment(node.comment)
    t_clk = t_data.get("clk")
    t_eval = t_data.get("eval")

    # Calculate time spent
    t_time_spent = None
    if node.parent and node.parent.parent:
        p_data = parse_comment(node.parent.parent.comment)
        p_clk = p_data.get("clk")
        if t_clk is not None and p_clk is not None:
            t_time_spent = p_clk - t_clk

    if t_time_spent is None:
        return None

    # Criteria 1: Speed
    is_fast = t_time_spent < speed_threshold or t_time_spent < 2

    # Criteria 2: Worsening position (or at least not improving significantly)
    is_not_improving = False
    move_diff = 0

    if t_eval is not None and node.parent:
        p_data_for_eval = parse_comment(node.parent.comment)
        p_eval = p_data_for_eval.get("eval")

        if p_eval is not None:
            if is_white_turn:
                move_diff = t_eval - p_eval
            else:
                move_diff = p_eval - t_eval

            # Allow neutral moves (diff < 50), reject improving moves
            if move_diff < 50:
                is_not_improving = True

    if is_fast and is_not_improving:
        move_num = (node.ply() + 1) // 2
        return {
            "move_san": node.san(),
            "move_number": move_num,
            "time_spent": t_time_spent,
            "eval": t_eval,
            "eval_diff": move_diff,
            "threshold_used": round(speed_threshold, 2),
        }

    return None
