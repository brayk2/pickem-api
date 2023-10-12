x = """
import React, { useEffect } from "react";
import { useDispatch, useSelector } from "react-redux";

const ${1:name} = (props) => {
  const dispatch = useDispatch();

  useEffect(() => {}, []);

  return <div></div>;
};

export default ${1:name};
"""


def convert(text: str):
    return text.split("\n")


if __name__ == "__main__":
    y = convert(x)
    print(y)
