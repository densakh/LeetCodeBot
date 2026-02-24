GLOBAL_DATA_QUERY = """
query globalData {
  userStatus {
    isSignedIn
    username
  }
}
"""

QUESTION_OF_TODAY_QUERY = """
query questionOfToday {
  activeDailyCodingChallengeQuestion {
    date
    link
    question {
      questionId
      questionFrontendId
      title
      titleSlug
      difficulty
      content
      topicTags { name slug }
      codeSnippets { lang langSlug code }
    }
  }
}
"""

PROBLEMSET_QUESTION_LIST_QUERY = """
query problemsetQuestionList(
  $categorySlug: String,
  $limit: Int,
  $skip: Int,
  $filters: QuestionListFilterInput
) {
  problemsetQuestionList: questionList(
    categorySlug: $categorySlug
    limit: $limit
    skip: $skip
    filters: $filters
  ) {
    total: totalNum
    questions: data {
      questionId
      questionFrontendId
      title
      titleSlug
      difficulty
      status
      topicTags { name slug }
      paidOnly: isPaidOnly
    }
  }
}
"""

QUESTION_DATA_QUERY = """
query questionData($titleSlug: String!) {
  question(titleSlug: $titleSlug) {
    questionId
    questionFrontendId
    title
    titleSlug
    content
    difficulty
    topicTags { name slug }
    codeSnippets { lang langSlug code }
    sampleTestCase
  }
}
"""

SUBMISSION_DETAILS_QUERY = """
query submissionDetails($submissionId: Int!) {
  submissionDetails(submissionId: $submissionId) {
    statusCode
    runtimeDisplay
    runtimePercentile
    memoryDisplay
    memoryPercentile
    totalCorrect
    totalTestcases
    expectedOutput
    codeOutput
  }
}
"""
