from agentic_framework.clarification import ClarificationEngine


def test_detect_vague_terms():
    engine = ClarificationEngine()
    prompt = "We need a fast, scalable system for many users."
    analysis = engine.analyze(prompt)
    assert len(analysis["vague_terms"]) > 0
    assert any(t["term"].lower() == "fast" for t in analysis["vague_terms"])
    assert any(t["category"] == "scalability" for t in analysis["vague_terms"])


def test_detect_missing_actors():
    engine = ClarificationEngine()
    prompt = "Users should be able to login and view their dashboard."
    analysis = engine.analyze(prompt)
    # Generic "users" should trigger a question about missing actor details
    assert len(analysis["questions"]) > 0


def test_generate_questions_ranked_by_priority():
    engine = ClarificationEngine()
    prompt = "We need a scalable system for thousands of concurrent users with fast response times."
    analysis = engine.analyze(prompt)
    questions = analysis["questions"]
    if len(questions) > 1:
        # Check that questions are sorted by priority descending
        priorities = [q["priority"] for q in questions]
        assert priorities == sorted(priorities, reverse=True)


def test_add_answer_to_question():
    engine = ClarificationEngine()
    prompt = "We need a fast system for many users."
    analysis = engine.analyze(prompt)
    engine.questions = analysis["questions"]

    if len(engine.questions) > 0:
        success = engine.add_answer(0, "We expect 10,000 concurrent users.")
        assert success is True
        assert engine.questions[0]["answer"] == "We expect 10,000 concurrent users."


def test_proceed_with_all_answers():
    engine = ClarificationEngine()
    prompt = "We need a fast system."
    analysis = engine.analyze(prompt)
    engine.questions = analysis["questions"]

    # Answer all questions
    for i, q in enumerate(engine.questions):
        engine.add_answer(i, f"Answer to {q['category']}")

    can_proceed, msg = engine.proceed_or_clarify()
    assert can_proceed is True
    assert "answered" in msg.lower()


def test_proceed_after_max_rounds():
    engine = ClarificationEngine(max_rounds=2)
    prompt = "We need a fast system for many users with high reliability."
    analysis = engine.analyze(prompt)
    engine.questions = analysis["questions"]

    # Simulate reaching max rounds without answering all questions
    for _ in range(2):
        can_proceed, msg = engine.proceed_or_clarify()

    # On the second call, should be forced to proceed and document assumptions
    assert can_proceed is True
    assert len(engine.assumptions) > 0


def test_summary():
    engine = ClarificationEngine()
    prompt = "We need a scalable system."
    analysis = engine.analyze(prompt)
    engine.questions = analysis["questions"]

    if len(engine.questions) > 0:
        engine.add_answer(0, "100k concurrent users")
        engine.proceed_or_clarify()

    summary = engine.summary()
    assert "round_count" in summary
    assert "questions_asked" in summary
    assert "answers" in summary
    assert "assumptions" in summary
