# AgentCore Runtime container. AgentCore runs linux/arm64: scripts/build_image.sh
# passes --platform linux/arm64 to buildx, so the platform is not pinned here.
FROM public.ecr.aws/docker/library/python:3.12-slim
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN pip install --no-cache-dir uv && uv export --no-dev --no-hashes -o requirements.txt \
 && pip install --no-cache-dir -r requirements.txt
COPY agent ./agent
ENV PYTHONUNBUFFERED=1
EXPOSE 8080
CMD ["python", "-m", "agent.main"]
