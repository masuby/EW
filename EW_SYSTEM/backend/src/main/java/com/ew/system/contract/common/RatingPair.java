package com.ew.system.contract.common;

public class RatingPair {
    public LikelihoodLevel likelihood;
    public ImpactLevel impact;

    public RatingPair() {}

    public RatingPair(LikelihoodLevel likelihood, ImpactLevel impact) {
        this.likelihood = likelihood;
        this.impact = impact;
    }

    public LikelihoodLevel getLikelihood() {
        return likelihood;
    }

    public void setLikelihood(LikelihoodLevel likelihood) {
        this.likelihood = likelihood;
    }

    public ImpactLevel getImpact() {
        return impact;
    }

    public void setImpact(ImpactLevel impact) {
        this.impact = impact;
    }
}

