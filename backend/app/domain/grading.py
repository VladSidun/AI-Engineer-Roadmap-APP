from app.domain.content import Pack


def grade(pack: Pack, answers: dict[str, list[str]]) -> tuple[int, dict[str, bool]]:
    questions = {question.id: question for question in pack.questions}
    if answers.keys() != questions.keys():
        raise ValueError("answer every question")
    results = {}
    for key, selected in answers.items():
        question = questions[key]
        ids = set(selected)
        if (not ids or len(ids) != len(selected) or ids - {o.id for o in question.options}
                or (len(question.correct) == 1 and len(ids) != 1)):
            raise ValueError("invalid option IDs")
        results[key] = ids == set(question.correct)
    return sum(results.values()), results


def passes(correct: int, total: int) -> bool:
    return total > 0 and correct * 5 >= total * 4
