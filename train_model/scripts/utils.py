import numpy as np

def calculate_wer(predictions, references):
    """
    Calculate the Word Error Rate (WER)
    WER = (Substitutions + Deletions + Insertions) / Total words in reference

    :param predictions: List of predicted transcripts
    :param references: List of reference transcripts (ground truth)
    :return: WER score as a float
    """
    total_wer = 0
    total_words = 0

    for pred, ref in zip(predictions, references):
        pred_words = pred.split()
        ref_words = ref.split()
        
        # Use numpy's edit distance function to calculate the minimum number of operations
        dp = np.zeros((len(ref_words) + 1, len(pred_words) + 1), dtype=int)

        for i in range(len(ref_words) + 1):
            dp[i][0] = i
        for j in range(len(pred_words) + 1):
            dp[0][j] = j

        for i in range(1, len(ref_words) + 1):
            for j in range(1, len(pred_words) + 1):
                if ref_words[i - 1] == pred_words[j - 1]:
                    dp[i][j] = dp[i - 1][j - 1]  # No operation required
                else:
                    dp[i][j] = min(dp[i - 1][j], dp[i][j - 1], dp[i - 1][j - 1]) + 1

        total_wer += dp[len(ref_words)][len(pred_words)]
        total_words += len(ref_words)

    return total_wer / total_words

# Example usage:
if __name__ == "__main__":
    predictions = ["this is an example", "word error rate calculation"]
    references = ["this is example", "word error rate compute"]
    
    wer_score = calculate_wer(predictions, references)
    print(f"WER: {wer_score:.2f}")
