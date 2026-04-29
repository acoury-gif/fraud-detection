from risk_rules import label_risk, score_transaction

# Baseline transaction: all signals at their safest values. score == 0.
BASE_TX = {
    "device_risk_score": 10,
    "is_international": 0,
    "amount_usd": 100,
    "velocity_24h": 1,
    "failed_logins_24h": 0,
    "prior_chargebacks": 0,
}


def tx(**overrides):
    return {**BASE_TX, **overrides}


# ---------------------------------------------------------------------------
# label_risk
# ---------------------------------------------------------------------------

class TestLabelRisk:
    def test_low_boundary(self):
        assert label_risk(0) == "low"
        assert label_risk(29) == "low"

    def test_medium_boundary(self):
        assert label_risk(30) == "medium"
        assert label_risk(59) == "medium"

    def test_high_boundary(self):
        assert label_risk(60) == "high"
        assert label_risk(100) == "high"


# ---------------------------------------------------------------------------
# device_risk_score
# ---------------------------------------------------------------------------

class TestDeviceRiskScore:
    def test_low_risk_device_adds_nothing(self):
        assert score_transaction(tx(device_risk_score=39)) == 0

    def test_moderate_risk_device_adds_10(self):
        assert score_transaction(tx(device_risk_score=40)) == 10
        assert score_transaction(tx(device_risk_score=69)) == 10

    def test_high_risk_device_adds_25(self):
        assert score_transaction(tx(device_risk_score=70)) == 25
        assert score_transaction(tx(device_risk_score=100)) == 25

    def test_high_risk_device_scores_higher_than_low_risk_device(self):
        # Regression guard: high device risk must raise the score, not lower it.
        assert score_transaction(tx(device_risk_score=85)) > score_transaction(tx(device_risk_score=10))

    def test_high_risk_device_scores_higher_than_moderate(self):
        assert score_transaction(tx(device_risk_score=70)) > score_transaction(tx(device_risk_score=40))


# ---------------------------------------------------------------------------
# is_international
# ---------------------------------------------------------------------------

class TestInternational:
    def test_domestic_adds_nothing(self):
        assert score_transaction(tx(is_international=0)) == 0

    def test_international_adds_15(self):
        assert score_transaction(tx(is_international=1)) == 15

    def test_international_scores_higher_than_domestic(self):
        # Regression guard: international transactions must increase risk.
        assert score_transaction(tx(is_international=1)) > score_transaction(tx(is_international=0))


# ---------------------------------------------------------------------------
# amount_usd
# ---------------------------------------------------------------------------

class TestAmountUsd:
    def test_small_amount_adds_nothing(self):
        assert score_transaction(tx(amount_usd=499)) == 0

    def test_medium_amount_adds_10(self):
        assert score_transaction(tx(amount_usd=500)) == 10
        assert score_transaction(tx(amount_usd=999)) == 10

    def test_large_amount_adds_25(self):
        assert score_transaction(tx(amount_usd=1000)) == 25
        assert score_transaction(tx(amount_usd=5000)) == 25

    def test_large_amount_scores_higher_than_medium_amount(self):
        assert score_transaction(tx(amount_usd=1000)) > score_transaction(tx(amount_usd=500))


# ---------------------------------------------------------------------------
# velocity_24h
# ---------------------------------------------------------------------------

class TestVelocity:
    def test_low_velocity_adds_nothing(self):
        assert score_transaction(tx(velocity_24h=2)) == 0

    def test_moderate_velocity_adds_5(self):
        assert score_transaction(tx(velocity_24h=3)) == 5
        assert score_transaction(tx(velocity_24h=5)) == 5

    def test_high_velocity_adds_20(self):
        assert score_transaction(tx(velocity_24h=6)) == 20
        assert score_transaction(tx(velocity_24h=15)) == 20

    def test_high_velocity_scores_higher_than_low_velocity(self):
        # Regression guard: burning through transactions fast must raise risk.
        assert score_transaction(tx(velocity_24h=10)) > score_transaction(tx(velocity_24h=1))

    def test_high_velocity_scores_higher_than_moderate_velocity(self):
        assert score_transaction(tx(velocity_24h=6)) > score_transaction(tx(velocity_24h=3))


# ---------------------------------------------------------------------------
# failed_logins_24h
# ---------------------------------------------------------------------------

class TestFailedLogins:
    def test_no_failed_logins_adds_nothing(self):
        assert score_transaction(tx(failed_logins_24h=1)) == 0

    def test_some_failed_logins_adds_10(self):
        assert score_transaction(tx(failed_logins_24h=2)) == 10
        assert score_transaction(tx(failed_logins_24h=4)) == 10

    def test_many_failed_logins_adds_20(self):
        assert score_transaction(tx(failed_logins_24h=5)) == 20
        assert score_transaction(tx(failed_logins_24h=10)) == 20

    def test_many_failed_logins_scores_higher_than_few(self):
        assert score_transaction(tx(failed_logins_24h=5)) > score_transaction(tx(failed_logins_24h=2))


# ---------------------------------------------------------------------------
# prior_chargebacks
# ---------------------------------------------------------------------------

class TestPriorChargebacks:
    def test_no_prior_chargebacks_adds_nothing(self):
        assert score_transaction(tx(prior_chargebacks=0)) == 0

    def test_one_prior_chargeback_adds_5(self):
        assert score_transaction(tx(prior_chargebacks=1)) == 5

    def test_multiple_prior_chargebacks_adds_20(self):
        assert score_transaction(tx(prior_chargebacks=2)) == 20
        assert score_transaction(tx(prior_chargebacks=5)) == 20

    def test_prior_chargebacks_scores_higher_than_none(self):
        # Regression guard: chargeback history must raise risk, not lower it.
        assert score_transaction(tx(prior_chargebacks=2)) > score_transaction(tx(prior_chargebacks=0))

    def test_more_chargebacks_scores_higher_than_one(self):
        assert score_transaction(tx(prior_chargebacks=2)) > score_transaction(tx(prior_chargebacks=1))


# ---------------------------------------------------------------------------
# Score clamping
# ---------------------------------------------------------------------------

class TestScoreClamping:
    def test_minimum_score_is_zero(self):
        assert score_transaction(BASE_TX) == 0

    def test_maximum_score_is_100(self):
        # Raw score: 25+15+25+20+20+20 = 125, must clamp to 100.
        worst = tx(
            device_risk_score=100,
            is_international=1,
            amount_usd=5000,
            velocity_24h=10,
            failed_logins_24h=10,
            prior_chargebacks=5,
        )
        assert score_transaction(worst) == 100


# ---------------------------------------------------------------------------
# Real-world scenarios
# ---------------------------------------------------------------------------

class TestRealWorldScenarios:
    def test_clean_domestic_transaction_is_low_risk(self):
        clean = tx(device_risk_score=8, amount_usd=45, velocity_24h=1)
        assert label_risk(score_transaction(clean)) == "low"

    def test_worst_case_fraudster_scores_100_and_is_high_risk(self):
        # Mirrors transaction 50011: confirmed fraud, every signal active.
        fraudster = tx(
            device_risk_score=85,
            is_international=1,
            amount_usd=1400,
            velocity_24h=8,
            failed_logins_24h=7,
            prior_chargebacks=1,
        )
        score = score_transaction(fraudster)
        assert score == 100
        assert label_risk(score) == "high"

    def test_high_value_domestic_purchase_is_medium_risk(self):
        # Large legitimate-looking purchase with moderate device risk.
        purchase = tx(device_risk_score=52, amount_usd=2200)
        assert label_risk(score_transaction(purchase)) == "medium"

    def test_international_high_velocity_large_amount_is_high_risk(self):
        # Classic card-not-present fraud pattern.
        suspicious = tx(
            device_risk_score=81,
            is_international=1,
            amount_usd=1250,
            velocity_24h=6,
            failed_logins_24h=5,
        )
        assert label_risk(score_transaction(suspicious)) == "high"

    def test_repeat_fraudster_is_high_risk_even_with_small_amount(self):
        # Account with 3 prior chargebacks making a small international purchase.
        repeat = tx(
            device_risk_score=77,
            is_international=1,
            amount_usd=50,
            velocity_24h=7,
            prior_chargebacks=3,
        )
        assert label_risk(score_transaction(repeat)) == "high"
