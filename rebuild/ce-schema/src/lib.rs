use serde::{Deserialize, Serialize};

#[derive(Debug, Deserialize, PartialEq, Serialize)]
pub struct Placeholder;

#[cfg(test)]
mod tests {
    use super::Placeholder;

    #[test]
    fn placeholder_round_trips_through_json() {
        let json = serde_json::to_string(&Placeholder).expect("serialize placeholder");
        let value: Placeholder = serde_json::from_str(&json).expect("deserialize placeholder");

        assert_eq!(value, Placeholder);
    }
}
