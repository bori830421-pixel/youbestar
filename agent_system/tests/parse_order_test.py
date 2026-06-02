def test_parse_order():
    result = skill_under_test.parse_order("苹果 2件")
    assert result[0]["name"] == "苹果"
    assert result[0]["qty"] == 2
