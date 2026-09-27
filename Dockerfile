FROM python:3.12.9-slim-bookworm@sha256:48a11b7ba705fd53bf15248d1f94d36c39549903c5d59edcfa2f3f84126e7b44
WORKDIR /artifact
COPY . .
RUN ./scripts/create_env.sh && ./scripts/check_env.sh
ENV PATH="/artifact/.stlt-venv/bin:${PATH}"
CMD ["./reproduce_paper_artifacts.sh"]
