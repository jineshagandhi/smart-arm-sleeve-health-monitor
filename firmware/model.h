#pragma once
#include <cstdarg>
namespace Eloquent {
    namespace ML {
        namespace Port {
            class LogisticRegression {
                public:
                    /**
                    * Predict class for features vector
                    */
                    int predict(float *x) {
                        float votes[3] = { -1.892517902092 ,-14.885793272547 ,0.103040997259  };
                        votes[0] += dot(x,   -0.319174960701  , 0.375159912041  , 0.697568192752  , -1.124648647364  , -0.155902844766 );
                        votes[1] += dot(x,   0.05417777711  , -0.056869738928  , -0.140945361597  , -1.284137772339  , 0.715292824482 );
                        votes[2] += dot(x,   0.007988720181  , 0.003749762014  , -0.087795943773  , 2.480953148739  , -0.953450665928 );
                        // return argmax of votes
                        uint8_t classIdx = 0;
                        float maxVotes = votes[0];

                        for (uint8_t i = 1; i < 3; i++) {
                            if (votes[i] > maxVotes) {
                                classIdx = i;
                                maxVotes = votes[i];
                            }
                        }

                        return classIdx;
                    }

                    /**
                    * Predict readable class name
                    */
                    const char* predictLabel(float *x) {
                        return idxToLabel(predict(x));
                    }

                    /**
                    * Convert class idx to readable name
                    */
                    const char* idxToLabel(uint8_t classIdx) {
                        switch (classIdx) {
                            case 0:
                            return "Good";
                            case 1:
                            return "Moderate";
                            case 2:
                            return "Risk";
                            default:
                            return "Houston we have a problem";
                        }
                    }

                protected:
                    /**
                    * Compute dot product
                    */
                    float dot(float *x, ...) {
                        va_list w;
                        va_start(w, 5);
                        float dot = 0.0;

                        for (uint16_t i = 0; i < 5; i++) {
                            const float wi = va_arg(w, double);
                            dot += x[i] * wi;
                        }

                        return dot;
                    }
                };
            }
        }
    }